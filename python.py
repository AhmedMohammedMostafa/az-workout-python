import json
import time
from datetime import datetime
import customtkinter as ctk
import requests
from dotenv import load_dotenv
import os
import google.generativeai as genai
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
from queue import Queue, Empty
from PIL import Image, ImageTk
from io import BytesIO

load_dotenv()
NUTRITIONIX_APP_ID = os.getenv('NUTRITIONIX_APP_ID')
NUTRITIONIX_API_KEY = os.getenv('NUTRITIONIX_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

class AZFoodLogger:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("AZ WORKOUT")
        self.window.geometry("1200x800")
        
        # Configure theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        # Configure window background
        self.window.configure(fg_color=("#222222", "#111111"))
        
        # Configure fonts
        self.title_font = ("Helvetica", 24, "bold")
        self.header_font = ("Helvetica", 18, "bold")
        self.text_font = ("Helvetica", 12)
        
        # Add loading indicator
        self.loading_var = ctk.StringVar(value="")
        self.loading_label = ctk.CTkLabel(
            self.window,
            textvariable=self.loading_var,
            font=self.text_font
        )
        self.loading_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Initialize async queue for API calls
        self.queue = Queue()
        
        # Continue with initialization
        if not self.load_user_profile():
            self.show_initial_setup()
        else:
            self.food_log = self.load_food_log()
            self.initialize_gemini()
            self.workout_plan = self.load_workout_plan()
            self.progress_data = self.load_progress_data()
            self.setup_gui()
            self.refresh_food_log()

    def initialize_gemini(self):
        try:
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            self.model = genai.GenerativeModel('gemini-pro')
            self.loading_var.set("")
            print("el gemini et3amal ya m3alem")
        except Exception as e:
            print(f"7asal error fel gemini ya ray2: {str(e)}")
            self.show_error(f"Failed to initialize AI: {str(e)}")

    @staticmethod
    def async_api_call(func):
        """Decorator for async API calls"""
        def wrapper(self, *args, **kwargs):
            # Get the appropriate loading variable based on the function name
            if 'workout' in func.__name__:
                loading_var = self.workout_loading_var
            elif 'ai_coach' in func.__name__:
                loading_var = self.ai_loading_var
            else:
                loading_var = self.loading_var
            
            loading_var.set("Processing...")
            
            def task():
                try:
                    result = func(self, *args, **kwargs)
                    self.queue.put(("success", result))
                except Exception as e:
                    self.queue.put(("error", str(e)))
                finally:
                    loading_var.set("")
            
            threading.Thread(target=task, daemon=True).start()
            self.window.after(100, self.check_queue)
        
        return wrapper

    def check_queue(self):
        """Check for completed API calls"""
        try:
            status, result = self.queue.get_nowait()
            if status == "error":
                self.show_error(result)
            else:
                self.handle_api_result(result)
        except Empty:
            self.window.after(100, self.check_queue)

    @async_api_call
    def generate_workout_plan(self):
        """Generate a workout plan using AI"""
        print("ya 7biby bgenerating el workout plan...")  # Egyptian Franko
        
        # Disable the generate button while processing
        self.generate_button.configure(state="disabled")
        
        # Validate user profile
        if not self.validate_user_profile():
            self.show_error("Please complete your profile first")
            self.generate_button.configure(state="normal")
            return
        
        user_stats = self.get_user_stats()
        prompt = f"""Create a detailed 5-day bodybuilding workout plan:

Overview:
- Rest days and schedule
- Progression guidelines
- Cardio recommendations
- Nutrition tips
- General guidelines

For each day (Days 1-5), provide:
Day [X]: [Focus]
- Detailed exercise list with sets, reps, and rest periods
- Form cues and tips
- Progression suggestions

User stats:
- Weight: {user_stats['weight']}kg
- Height: {user_stats['height']}cm
- Goal: {user_stats['goal']}
- Experience: {user_stats.get('experience', 'Intermediate')}

Please provide a comprehensive and detailed plan with clear formatting."""
        
        try:
            print("Sending request to AI model...")  # Debug print
            response = self.model.generate_content(prompt)
            print("Received response from AI model")  # Debug print
            return response.text
        except Exception as e:
            print(f"Error in generate_workout_plan: {str(e)}")  # Debug print
            self.show_error(f"Error generating workout plan: {str(e)}")
            self.generate_button.configure(state="normal")
            return None

    def validate_user_profile(self):
        """Validate that required user profile fields are filled"""
        profile = self.load_user_profile()
        required_fields = ['weight', 'height', 'goal']
        return all(field in profile and profile[field] for field in required_fields)

    def setup_gui(self):
        # Create main containers with padding
        self.left_frame = ctk.CTkFrame(
            self.window,
            width=300,
            fg_color=("#2b2b2b", "#1a1a1a"),  # Darker theme
            corner_radius=15
        )
        self.left_frame.pack(side="left", fill="y", padx=20, pady=20)
        
        self.right_frame = ctk.CTkFrame(
            self.window,
            fg_color=("#333333", "#202020"),  # Slightly lighter than left frame
            corner_radius=15
        )
        self.right_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        # Add logo with click counter for easter egg
        self.logo_clicks = 0
        self.last_click_time = 0
        
        logo_frame = ctk.CTkFrame(
            self.left_frame,
            fg_color="transparent"
        )
        logo_frame.pack(pady=20)
        
        logo_label = ctk.CTkLabel(
            logo_frame,
            text="AZ WORKOUT",
            font=("Helvetica", 24, "bold"),
            text_color=("#ffffff", "#ffffff")
        )
        logo_label.pack()
        
        # Add click binding for easter egg
        logo_label.bind("<Button-1>", self.logo_click)
        
        # User profile summary with modern styling
        self.setup_user_summary()
        
        # Add tabs with modern styling
        self.tabview = ctk.CTkTabview(
            self.right_frame,
            fg_color=("gray95", "#202020"),
            segmented_button_fg_color=("#333333", "#2b2b2b"),
            segmented_button_selected_color=("#4a4a4a", "#3a3a3a"),
            segmented_button_selected_hover_color=("#555555", "#444444"),
            segmented_button_unselected_hover_color=("#444444", "#333333"),
            text_color=("#ffffff", "#ffffff"),
            corner_radius=10
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add tabs with modern icons
        self.tab_food = self.tabview.add("🍎 Food Logger")
        self.tab_workout = self.tabview.add("💪 Workout Plan")
        self.tab_ai = self.tabview.add("🤖 AI Coach")
        
        self.setup_food_log_section(self.tab_food)
        self.setup_workout_section(self.tab_workout)
        self.setup_ai_section(self.tab_ai)

    def logo_click(self, event):
        current_time = time.time()
        if current_time - self.last_click_time > 2:  # Reset counter if more than 2 seconds between clicks
            self.logo_clicks = 1
        else:
            self.logo_clicks += 1
        
        self.last_click_time = current_time
        
        if self.logo_clicks == 3:
            self.show_easter_egg()
            self.logo_clicks = 0

    def show_easter_egg(self):
        # Create popup with love effect
        popup = ctk.CTkToplevel()
        popup.geometry("400x200")
        popup.title("❤️")
        
        # Make popup semi-transparent and borderless
        popup.attributes('-alpha', 0.9)
        popup.overrideredirect(True)
        
        # Center the popup
        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f'+{x}+{y}')
        
        # Create main frame with gradient effect
        main_frame = ctk.CTkFrame(
            popup,
            fg_color=("#2b2b2b", "#1a1a1a"),
            corner_radius=20
        )
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add text with animation
        text = "Best doctor is doctor bassam ❤️"
        label = ctk.CTkLabel(
            main_frame,
            text=text,
            font=("Helvetica", 20, "bold"),
            text_color=("#ffffff", "#ffffff")
        )
        label.pack(expand=True)
        
        # Add close button
        close_btn = ctk.CTkButton(
            main_frame,
            text="❌",
            width=30,
            command=popup.destroy,
            fg_color="transparent",
            hover_color=("#3a3a3a", "#2a2a2a")
        )
        close_btn.pack(pady=10)
        
        # Add fade-in effect
        for i in range(0, 10):
            popup.attributes('-alpha', i/10)
            popup.update()
            time.sleep(0.05)
        
        # Auto-close after 3 seconds
        popup.after(3000, lambda: popup.destroy())

    def setup_user_summary(self):
        # Profile section with modern styling
        profile = self.load_user_profile()
        
        # User name and basic info
        name_frame = ctk.CTkFrame(
            self.left_frame,
            fg_color="transparent"
        )
        name_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(
            name_frame,
            text=profile['name'],
            font=("Helvetica", 20, "bold"),
            text_color=("#ffffff", "#ffffff")
        ).pack(pady=5)
        
        # Current stats with modern cards
        stats = [
            ("Current Weight", f"{profile['weight']} kg"),
            ("Height", f"{profile['height']} cm"),
            ("Goal", profile['goal']),
            ("Activity Level", profile['activity_level'])
        ]
        
        for label, value in stats:
            card = ctk.CTkFrame(
                self.left_frame,
                fg_color=("#333333", "#252525"),
                corner_radius=10
            )
            card.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(
                card,
                text=label,
                font=("Helvetica", 12),
                text_color=("#bbbbbb", "#bbbbbb")
            ).pack(anchor="w", padx=10, pady=(5, 0))
            
            ctk.CTkLabel(
                card,
                text=value,
                font=("Helvetica", 14, "bold"),
                text_color=("#ffffff", "#ffffff")
            ).pack(anchor="w", padx=10, pady=(0, 5))
        
        # Add macro tracking with modern progress bars
        self.create_macro_progress_bars(self.left_frame)

    def create_macro_progress_bars(self, parent):
        for widget in parent.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget.winfo_children() and isinstance(widget.winfo_children()[0], ctk.CTkLabel) and widget.winfo_children()[0].cget("text") == "Today's Progress":
                widget.destroy()

        progress_frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )
        progress_frame.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(
            progress_frame,
            text="Today's Progress",
            font=("Helvetica", 16, "bold"),
            text_color=("#ffffff", "#ffffff")
        ).pack(pady=(0, 10))
        
        profile = self.load_user_profile()
        todays_log = self.get_todays_log()
        
        try:
            current = {
                'calories': sum(float(food.get('calories', 0)) for food in todays_log),
                'protein': sum(float(food.get('protein', 0)) for food in todays_log),
                'carbs': sum(float(food.get('carbs', 0)) for food in todays_log),
                'fats': sum(float(food.get('fats', 0)) for food in todays_log)
            }
            
            print(f"el total calories: {current['calories']}")
            print(f"el total protein: {current['protein']}")
            print(f"el total carbs: {current['carbs']}")
            print(f"el total fats: {current['fats']}")
            
        except Exception as e:
            print(f"7asal error fel 7esabat: {str(e)}")
            current = {'calories': 0, 'protein': 0, 'carbs': 0, 'fats': 0}
        
        metrics = [
            ("Calories", current['calories'], float(profile.get('daily_calories', 2000)), "kcal", "#FF6B6B"),
            ("Protein", current['protein'], float(profile.get('daily_protein', 150)), "g", "#4ECDC4"),
            ("Carbs", current['carbs'], float(profile.get('daily_carbs', 250)), "g", "#45B7D1"),
            ("Fats", current['fats'], float(profile.get('daily_fats', 65)), "g", "#96CEB4")
        ]
        
        for label, current_val, goal, unit, color in metrics:
            metric_frame = ctk.CTkFrame(
                progress_frame,
                fg_color=("#333333", "#252525"),
                corner_radius=10
            )
            metric_frame.pack(fill="x", pady=5)
            
            header_frame = ctk.CTkFrame(
                metric_frame,
                fg_color="transparent"
            )
            header_frame.pack(fill="x", padx=10, pady=(5, 0))
            
            ctk.CTkLabel(
                header_frame,
                text=label,
                font=("Helvetica", 12),
                text_color=("#bbbbbb", "#bbbbbb")
            ).pack(side="left")
            
            ctk.CTkLabel(
                header_frame,
                text=f"{int(current_val)}/{int(goal)}{unit}",
                font=("Helvetica", 12),
                text_color=("#ffffff", "#ffffff")
            ).pack(side="right")
            
            progress = ctk.CTkProgressBar(
                metric_frame,
                progress_color=color,
                fg_color=("#2b2b2b", "#1a1a1a")
            )
            progress.pack(fill="x", padx=10, pady=(5, 10))
            
            try:
                progress_value = min(float(current_val)/float(goal), 1.0) if float(goal) > 0 else 0
                progress.set(progress_value)
            except (ValueError, ZeroDivisionError) as e:
                print(f"Error setting progress bar: {str(e)}")
                progress.set(0)

    def setup_food_log_section(self, parent):
        main_container = ctk.CTkFrame(parent)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)
        
        search_frame = ctk.CTkFrame(main_container, fg_color=("#333333", "#252525"))
        search_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        search_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(
            search_frame, 
            placeholder_text="Search food...",
            height=40,
            font=("Helvetica", 14)
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkButton(
            search_frame,
            text="Search",
            command=self.search_food,
            height=40,
            font=("Helvetica", 14),
            fg_color=("#4a4a4a", "#3a3a3a"),
            hover_color=("#555555", "#444444")
        ).grid(row=0, column=1, padx=10, pady=10)
        
        meals_container = ctk.CTkFrame(main_container)
        meals_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        meals_container.grid_columnconfigure(0, weight=1)
        meals_container.grid_columnconfigure(1, weight=1)
        meals_container.grid_rowconfigure(1, weight=1)
        
        self.meal_sections = {}
        self.meal_calories_labels = {}
        meal_types = ["Breakfast", "Lunch"]
        
        for i, meal_type in enumerate(meal_types):
            section_frame = ctk.CTkFrame(meals_container, fg_color=("#333333", "#252525"))
            section_frame.grid(row=0, column=i, sticky="nsew", padx=5, pady=5)
            section_frame.grid_columnconfigure(0, weight=1)
            section_frame.grid_rowconfigure(1, weight=1)
            
            header_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
            header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
            header_frame.grid_columnconfigure(0, weight=1)
            
            ctk.CTkLabel(
                header_frame,
                text=meal_type,
                font=("Helvetica", 16, "bold")
            ).grid(row=0, column=0, sticky="w", padx=5)
            
            calories_label = ctk.CTkLabel(
                header_frame,
                text="0 kcal",
                font=("Helvetica", 14)
            )
            calories_label.grid(row=0, column=1, sticky="e", padx=5)
            
            self.meal_calories_labels[meal_type] = calories_label
            
            food_frame = ctk.CTkScrollableFrame(
                section_frame,
                fg_color=("#2b2b2b", "#1a1a1a")
            )
            food_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
            food_frame.grid_columnconfigure(0, weight=1)
            
            self.meal_sections[meal_type] = food_frame

    def setup_workout_section(self, parent):
        # Main container with modern styling
        plan_frame = ctk.CTkFrame(
            parent,
            fg_color=("#2b2b2b", "#1a1a1a")
        )
        plan_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header section
        header_frame = ctk.CTkFrame(
            plan_frame,
            fg_color="transparent"
        )
        header_frame.pack(fill="x", padx=10, pady=10)
        
        # Title
        ctk.CTkLabel(
            header_frame,
            text="Workout Planner",
            font=("Helvetica", 24, "bold")
        ).pack(side="left", padx=10)
        
        # Loading indicator
        self.workout_loading_var = ctk.StringVar(value="")
        self.workout_loading_label = ctk.CTkLabel(
            header_frame,
            textvariable=self.workout_loading_var,
            font=("Helvetica", 14)
        )
        self.workout_loading_label.pack(side="left", padx=10)
        
        # Generate button with modern styling
        self.generate_button = ctk.CTkButton(
            header_frame,
            text="Generate New Plan",
            command=self.generate_workout_plan,
            font=("Helvetica", 14, "bold"),
            height=40,
            fg_color=("#4a4a4a", "#3a3a3a"),
            hover_color=("#555555", "#444444")
        )
        self.generate_button.pack(side="right", padx=10)
        
        # Create scrollable text widget for the workout plan
        self.workout_text = ctk.CTkTextbox(
            plan_frame,
            font=("Helvetica", 14),
            fg_color=("#2b2b2b", "#1a1a1a"),
            text_color="white",
            wrap="word"
        )
        self.workout_text.pack(fill="both", expand=True, padx=10, pady=10)

    def setup_ai_section(self, parent):
        # Main container
        ai_frame = ctk.CTkFrame(
            parent,
            fg_color=("#2b2b2b", "#1a1a1a")
        )
        ai_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ctk.CTkFrame(
            ai_frame,
            fg_color="transparent"
        )
        header_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            header_frame,
            text="AI Fitness Coach",
            font=("Helvetica", 24, "bold")
        ).pack(side="left", padx=10)
        
        # Chat container
        chat_frame = ctk.CTkFrame(
            ai_frame,
            fg_color=("#333333", "#252525")
        )
        chat_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Chat history
        self.chat_history = ctk.CTkTextbox(
            chat_frame,
            font=("Helvetica", 14),
            fg_color=("#2b2b2b", "#1a1a1a"),
            text_color="white"
        )
        self.chat_history.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Input area
        input_frame = ctk.CTkFrame(
            ai_frame,
            fg_color=("#333333", "#252525")
        )
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Question input
        self.ai_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="Ask your fitness question...",
            font=("Helvetica", 14),
            height=40
        )
        self.ai_input.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        # Loading indicator
        self.ai_loading_var = ctk.StringVar(value="")
        self.ai_loading_label = ctk.CTkLabel(
            input_frame,
            textvariable=self.ai_loading_var,
            font=("Helvetica", 14)
        )
        self.ai_loading_label.pack(side="left", padx=10)
        
        # Send button
        self.ask_button = ctk.CTkButton(
            input_frame,
            text="Ask",
            command=self.ask_ai_coach,
            font=("Helvetica", 14, "bold"),
            height=40,
            width=100,
            fg_color=("#4a4a4a", "#3a3a3a"),
            hover_color=("#555555", "#444444")
        )
        self.ask_button.pack(side="right", padx=10, pady=10)
        
        # Add validation and enter key binding
        self.ai_input.bind("<Return>", lambda e: self.ask_ai_coach())

    @async_api_call
    def ask_ai_coach(self):
        # Disable the ask button while processing
        self.ask_button.configure(state="disabled")
        
        question = self.ai_input.get().strip()
        
        # Validate input
        if not question:
            self.show_error("Please enter a question")
            self.ask_button.configure(state="normal")
            return
        
        # Add user question to chat history
        self.chat_history.insert("end", f"\nYou: {question}\n\n")
        self.chat_history.see("end")
        
        # Clear input
        self.ai_input.delete(0, "end")
        
        try:
            # Get AI response
            response = self.model.generate_content(question)
            return response.text
            
        except Exception as e:
            self.show_error(f"Error getting AI response: {str(e)}")
            self.ask_button.configure(state="normal")

    def run(self):
        self.window.mainloop()

    def get_food_details(self, item, quantity=1, serving_size="100g", meal="Snack", notes=""):
        """Get detailed nutritional information for a food item"""
        headers = {
            "x-app-id": NUTRITIONIX_APP_ID,
            "x-app-key": NUTRITIONIX_API_KEY,
            "x-remote-user-id": "0"
        }
        
        data = {
            "query": f"{quantity} {serving_size} {item['food_name']}"
        }
        
        try:
            response = requests.post(
                "https://trackapi.nutritionix.com/v2/natural/nutrients",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'foods' in result and len(result['foods']) > 0:
                    food_data = result['foods'][0]
                    
                    # Create food entry
                    food_entry = {
                        'food': item['food_name'],
                        'quantity': quantity,
                        'serving_size': serving_size,
                        'meal': meal,
                        'notes': notes,
                        'calories': round(food_data.get('nf_calories', 0)),
                        'protein': round(food_data.get('nf_protein', 0)),
                        'carbs': round(food_data.get('nf_total_carbohydrate', 0)),
                        'fats': round(food_data.get('nf_total_fat', 0)),
                        'date': datetime.now().strftime("%Y-%m-%d"),
                        'id': str(time.time())
                    }
                    
                    # Add to food log
                    self.add_food_to_log(food_entry)
                else:
                    self.show_error("No nutritional information found for this food")
            else:
                self.show_error("Failed to fetch nutritional information")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def load_food_log(self):
        """Load the food log from file"""
        try:
            with open("food_log.json", "r") as f:
                log = json.load(f)
                print(f"Loaded {len(log)} entries from food log")
                return log
        except FileNotFoundError:
            print("mesh la2y el food log file, ha3mel wa7ed gedid")
            return []
        except Exception as e:
            print(f"7asal error fel loading bta3 el food log: {str(e)}")
            return []

    def load_user_profile(self):
        """Load the user profile from file"""
        try:
            with open("user_profile.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}  # Return empty dict if file doesn't exist yet
        except json.JSONDecodeError:
            self.show_error("Error reading user profile file")
            return {}

    def load_workout_plan(self):
        """Load the workout plan from file"""
        try:
            with open("workout_plan.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}  # Return empty dict if file doesn't exist yet
        except json.JSONDecodeError:
            self.show_error("Error reading workout plan file")
            return {}

    def load_progress_data(self):
        """Load the progress data from file"""
        try:
            with open("progress_data.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}  # Return empty dict if file doesn't exist yet
        except json.JSONDecodeError:
            self.show_error("Error reading progress data file")
            return {}

    def get_todays_log(self):
        today = datetime.now().strftime("%Y-%m-%d")
        todays_entries = [entry for entry in self.food_log if isinstance(entry, dict) and entry.get('date') == today]
        print(f"3adad el entries el naharda: {len(todays_entries)}")
        for entry in todays_entries:
            print(f"Entry: {entry.get('food')} - Calories: {entry.get('calories')} - Protein: {entry.get('protein')}")
        return todays_entries

    def search_food(self):
        """Search for food items using Nutritionix API"""
        query = self.search_entry.get().strip()
        
        if not query:
            self.show_error("Please enter a food item to search")
            return
        
        headers = {
            "x-app-id": NUTRITIONIX_APP_ID,
            "x-app-key": NUTRITIONIX_API_KEY,
            "x-remote-user-id": "0"
        }
        
        try:
            response = requests.get(
                f"https://trackapi.nutritionix.com/v2/search/instant?query={query}",
                headers=headers
            )
            
            if response.status_code == 200:
                results = response.json()
                self.display_search_results(results.get('common', []))
            else:
                self.show_error("Failed to fetch food items")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def display_search_results(self, results):
        """Display search results in a popup window"""
        # Create popup window
        popup = ctk.CTkToplevel()
        popup.title("Search Results")
        popup.geometry("600x400")
        
        # Create scrollable frame for results
        results_frame = ctk.CTkScrollableFrame(
            popup,
            fg_color=("#2b2b2b", "#1a1a1a")
        )
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for item in results[:10]:  # Limit to 10 results
            # Create frame for each food item
            item_frame = ctk.CTkFrame(
                results_frame,
                fg_color=("#333333", "#252525")
            )
            item_frame.pack(fill="x", padx=5, pady=2)
            
            # Try to get food image
            try:
                image_url = item.get('photo', {}).get('thumb', None)
                if image_url:
                    response = requests.get(image_url)
                    img = Image.open(BytesIO(response.content))
                    img = img.resize((50, 50), Image.Resampling.LANCZOS)
                    # Convert to CTkImage
                    ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(50, 50))
                    
                    img_label = ctk.CTkLabel(
                        item_frame,
                        image=ctk_image,
                        text=""
                    )
                    img_label.pack(side="left", padx=5, pady=5)
            except Exception as e:
                print(f"Error loading image: {e}")
            
            # Food name
            ctk.CTkLabel(
                item_frame,
                text=item['food_name'].title(),
                font=("Helvetica", 14)
            ).pack(side="left", padx=10, pady=5)
            
            # Add food button
            ctk.CTkButton(
                item_frame,
                text="Add",
                command=lambda i=item: self.show_add_food_dialog(i),
                width=60,
                font=("Helvetica", 12)
            ).pack(side="right", padx=10, pady=5)
            
            # View details button
            ctk.CTkButton(
                item_frame,
                text="Details",
                command=lambda i=item: self.show_food_details(i),
                width=60,
                font=("Helvetica", 12)
            ).pack(side="right", padx=10, pady=5)

    def show_add_food_dialog(self, food_item):
        """Show dialog to add food with quantity and meal type"""
        dialog = ctk.CTkToplevel()
        dialog.title(f"Add {food_item['food_name'].title()}")
        dialog.geometry("400x500")
        
        # Quantity frame
        quantity_frame = ctk.CTkFrame(dialog)
        quantity_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            quantity_frame,
            text="Quantity (g):",
            font=("Helvetica", 14)
        ).pack(side="left", padx=5)
        
        quantity_var = ctk.StringVar(value="100")
        quantity_entry = ctk.CTkEntry(
            quantity_frame,
            textvariable=quantity_var,
            width=100
        )
        quantity_entry.pack(side="right", padx=5)
        
        # Meal type selection
        meal_frame = ctk.CTkFrame(dialog)
        meal_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            meal_frame,
            text="Meal:",
            font=("Helvetica", 14)
        ).pack(side="left", padx=5)
        
        meal_var = ctk.StringVar(value="Snacks")
        meal_options = ["Breakfast", "Lunch", "Dinner", "Snacks"]
        
        for meal in meal_options:
            ctk.CTkRadioButton(
                meal_frame,
                text=meal,
                variable=meal_var,
                value=meal
            ).pack(side="left", padx=5)
        
        # Notes
        notes_frame = ctk.CTkFrame(dialog)
        notes_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            notes_frame,
            text="Notes:",
            font=("Helvetica", 14)
        ).pack(anchor="w", padx=5)
        
        notes_text = ctk.CTkTextbox(
            notes_frame,
            height=100
        )
        notes_text.pack(fill="x", padx=5, pady=5)
        
        # Add button
        ctk.CTkButton(
            dialog,
            text="Add Food",
            command=lambda: self.add_food_item(
                food_item,
                quantity_var.get(),
                meal_var.get(),
                notes_text.get("1.0", "end-1c"),
                dialog
            )
        ).pack(pady=20)

    def add_food_item(self, food_item, quantity, meal_type, notes, dialog):
        """Add food item to the log"""
        try:
            quantity = float(quantity)
            
            # Get nutritional info
            headers = {
                "x-app-id": NUTRITIONIX_APP_ID,
                "x-app-key": NUTRITIONIX_API_KEY,
                "x-remote-user-id": "0"
            }
            
            data = {
                "query": f"{quantity}g {food_item['food_name']}"
            }
            
            response = requests.post(
                "https://trackapi.nutritionix.com/v2/natural/nutrients",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'foods' in result and len(result['foods']) > 0:
                    food_data = result['foods'][0]
                    
                    # Create food entry with all required fields
                    food_entry = {
                        'food': food_item['food_name'],
                        'quantity': quantity,  # Make sure quantity is included
                        'meal': meal_type,
                        'notes': notes,
                        'calories': round(food_data.get('nf_calories', 0)),
                        'protein': round(food_data.get('nf_protein', 0)),
                        'carbs': round(food_data.get('nf_total_carbohydrate', 0)),
                        'fats': round(food_data.get('nf_total_fat', 0)),
                        'date': datetime.now().strftime("%Y-%m-%d"),
                        'id': str(time.time()),
                        'photo': food_item.get('photo', {})
                    }
                    
                    # Add to food log
                    if not hasattr(self, 'food_log'):
                        self.food_log = []
                    self.food_log.append(food_entry)
                    self.save_food_log()
                    
                    # Close dialog
                    dialog.destroy()
                    
                    # Refresh food log display
                    self.refresh_food_log()
                else:
                    self.show_error("No nutritional information found for this food")
            else:
                self.show_error("Failed to fetch nutritional information")
            
        except ValueError:
            self.show_error("Please enter a valid quantity")
        except Exception as e:
            print(f"7asal error fel adding: {str(e)}")
            self.show_error(f"Error: {str(e)}")

    def delete_food_entry(self, entry):
        """Delete a food entry from the log"""
        if 'id' in entry:
            self.food_log = [e for e in self.food_log if e.get('id') != entry['id']]
            self.save_food_log()
            print(f"keda mesa7t el entry bta3 {entry.get('food', 'unknown')} men el food log")
            self.refresh_food_log()

    def show_edit_food_dialog(self, entry):
        """Show dialog to edit food entry"""
        dialog = ctk.CTkToplevel()
        dialog.title(f"Edit {entry['food']}")
        dialog.geometry("400x500")
        
        # Quantity frame
        quantity_frame = ctk.CTkFrame(dialog)
        quantity_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            quantity_frame,
            text="Quantity (g):",
            font=("Helvetica", 14)
        ).pack(side="left", padx=5)
        
        quantity_var = ctk.StringVar(value=str(entry['quantity']))
        quantity_entry = ctk.CTkEntry(
            quantity_frame,
            textvariable=quantity_var,
            width=100
        )
        quantity_entry.pack(side="right", padx=5)
        
        # Meal type selection
        meal_frame = ctk.CTkFrame(dialog)
        meal_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            meal_frame,
            text="Meal:",
            font=("Helvetica", 14)
        ).pack(side="left", padx=5)
        
        meal_var = ctk.StringVar(value=entry.get('meal', 'Lunch'))
        meal_options = ["Breakfast", "Lunch"]
        
        for meal in meal_options:
            ctk.CTkRadioButton(
                meal_frame,
                text=meal,
                variable=meal_var,
                value=meal
            ).pack(side="left", padx=5)
        
        # Notes
        notes_frame = ctk.CTkFrame(dialog)
        notes_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            notes_frame,
            text="Notes:",
            font=("Helvetica", 14)
        ).pack(anchor="w", padx=5)
        
        notes_text = ctk.CTkTextbox(
            notes_frame,
            height=100
        )
        notes_text.pack(fill="x", padx=5, pady=5)
        notes_text.insert("1.0", entry.get('notes', ''))
        
        # Update button
        ctk.CTkButton(
            dialog,
            text="Update Food",
            command=lambda: self.update_food_entry(
                entry,
                quantity_var.get(),
                meal_var.get(),
                notes_text.get("1.0", "end-1c"),
                dialog
            )
        ).pack(pady=20)

    def update_food_entry(self, old_entry, quantity, meal_type, notes, dialog):
        """Update an existing food entry"""
        try:
            quantity = float(quantity)
            
            # Get nutritional info
            headers = {
                "x-app-id": NUTRITIONIX_APP_ID,
                "x-app-key": NUTRITIONIX_API_KEY,
                "x-remote-user-id": "0"
            }
            
            data = {
                "query": f"{quantity}g {old_entry['food']}"
            }
            
            response = requests.post(
                "https://trackapi.nutritionix.com/v2/natural/nutrients",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'foods' in result and len(result['foods']) > 0:
                    food_data = result['foods'][0]
                    
                    # Update entry
                    for entry in self.food_log:
                        if entry.get('id') == old_entry['id']:
                            entry.update({
                                'quantity': quantity,
                                'meal': meal_type,
                                'notes': notes,
                                'calories': round(food_data.get('nf_calories', 0)),
                                'protein': round(food_data.get('nf_protein', 0)),
                                'carbs': round(food_data.get('nf_total_carbohydrate', 0)),
                                'fats': round(food_data.get('nf_total_fat', 0))
                            })
                            break
                    
                    self.save_food_log()
                    dialog.destroy()
                    self.refresh_food_log()
                else:
                    self.show_error("No nutritional information found for this food")
            else:
                self.show_error("Failed to fetch nutritional information")
            
        except ValueError:
            self.show_error("Please enter a valid quantity")
        except Exception as e:
            print(f"7asal error fel updating: {str(e)}")
            self.show_error(f"Error: {str(e)}")

    def save_food_log(self):
        """Save the food log to file"""
        try:
            with open("food_log.json", "w") as f:
                json.dump(self.food_log, f)
        except Exception as e:
            self.show_error(f"Error saving food log: {str(e)}")

    def refresh_food_log(self):
        """Refresh the food log display"""
        for section in self.meal_sections.values():
            for widget in section.winfo_children():
                widget.destroy()
        
        todays_log = self.get_todays_log()
        meal_calories = {"Breakfast": 0, "Lunch": 0}
        
        for entry in todays_log:
            meal_type = entry.get('meal', 'Lunch')
            if meal_type in self.meal_sections:
                self.create_food_entry_widget(self.meal_sections[meal_type], entry)
                try:
                    calories = float(entry.get('calories', 0))
                    meal_calories[meal_type] += calories
                except (ValueError, TypeError):
                    print(f"Error converting calories for entry: {entry}")
        
        for meal_type, calories in meal_calories.items():
            if meal_type in self.meal_calories_labels:
                self.meal_calories_labels[meal_type].configure(text=f"{int(calories)} kcal")
        
        self.create_macro_progress_bars(self.left_frame)

    def create_food_entry_widget(self, parent, entry):
        """Create a widget for a food entry"""
        try:
            entry_frame = ctk.CTkFrame(
                parent,
                fg_color=("#333333", "#252525")
            )
            entry_frame.pack(fill="x", padx=5, pady=2)
            entry_frame.grid_columnconfigure(1, weight=1)  # Make food info expandable
            
            # Try to get food image
            try:
                if 'photo' in entry:
                    image_url = entry['photo'].get('thumb', None)
                    if image_url:
                        response = requests.get(image_url)
                        img = Image.open(BytesIO(response.content))
                        img = img.resize((40, 40), Image.Resampling.LANCZOS)
                        ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
                        
                        img_label = ctk.CTkLabel(
                            entry_frame,
                            image=ctk_image,
                            text=""
                        )
                        img_label.grid(row=0, column=0, rowspan=2, padx=5, pady=5)
            except Exception as e:
                print(f"Error loading image: {e}")
            
            # Food info (name, quantity, calories)
            info_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
            info_frame.grid(row=0, column=1, sticky="ew", padx=5)
            info_frame.grid_columnconfigure(0, weight=1)
            
            # Food name
            food_name = entry.get('food', 'Unknown Food')
            ctk.CTkLabel(
                info_frame,
                text=food_name,
                font=("Helvetica", 12, "bold")
            ).grid(row=0, column=0, sticky="w")
            
            # Quantity (with fallback)
            quantity = entry.get('quantity', 0)
            ctk.CTkLabel(
                info_frame,
                text=f"{quantity}g",
                font=("Helvetica", 12)
            ).grid(row=1, column=0, sticky="w")
            
            # Calories (if available)
            calories = entry.get('calories', 0)
            if calories:
                ctk.CTkLabel(
                    info_frame,
                    text=f"{calories} kcal",
                    font=("Helvetica", 12)
                ).grid(row=0, column=1, sticky="e", padx=5)
            
            # Buttons frame
            buttons_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
            buttons_frame.grid(row=0, column=2, padx=5, pady=5)
            
            # Edit button
            ctk.CTkButton(
                buttons_frame,
                text="Edit",
                command=lambda: self.show_edit_food_dialog(entry),
                width=60,
                height=30,
                font=("Helvetica", 12)
            ).grid(row=0, column=0, padx=2)
            
            # Delete button
            ctk.CTkButton(
                buttons_frame,
                text="Delete",
                command=lambda: self.delete_food_entry(entry),
                width=60,
                height=30,
                font=("Helvetica", 12),
                fg_color="red",
                hover_color="#aa0000"
            ).grid(row=0, column=1, padx=2)
            
        except Exception as e:
            print(f"Error creating food entry widget: {e}")
            self.show_error(f"Error displaying food entry: {str(e)}")

    def show_error(self, message):
        """Display error message in a popup"""
        # Print error message to console for debugging
        print(f"Error: {message}")
        
        error_window = ctk.CTkToplevel()
        error_window.title("Error")
        error_window.geometry("400x200")
        
        # Make window modal
        error_window.transient(self.window)
        error_window.grab_set()
        
        # Center the window
        error_window.update_idletasks()
        width = error_window.winfo_width()
        height = error_window.winfo_height()
        x = (error_window.winfo_screenwidth() // 2) - (width // 2)
        y = (error_window.winfo_screenheight() // 2) - (height // 2)
        error_window.geometry(f'+{x}+{y}')
        
        # Add error message
        message_label = ctk.CTkLabel(
            error_window,
            text=message,
            font=("Helvetica", 14),
            wraplength=350
        )
        message_label.pack(expand=True, padx=20, pady=(20, 10))
        
        # Add OK button
        ok_button = ctk.CTkButton(
            error_window,
            text="OK",
            command=error_window.destroy,
            width=100
        )
        ok_button.pack(pady=(0, 20))
        
        # Auto-close after 5 seconds
        error_window.after(5000, error_window.destroy)

    def get_user_stats(self):
        """Get user statistics from the profile"""
        profile = self.load_user_profile()
        
        # Return basic stats needed for workout plan generation
        return {
            'weight': profile.get('weight', 0),
            'height': profile.get('height', 0),
            'goal': profile.get('goal', 'general fitness'),
            'experience': profile.get('experience', 'Intermediate'),
            'activity_level': profile.get('activity_level', 'Moderate')
        }

    def handle_api_result(self, result):
        """Handle results from async API calls"""
        if not result:
            return
        
        # Handle workout plan generation result
        if isinstance(result, str) and "workout plan" in result.lower():
            try:
                print("el workout plan geh ya m3alem:", result)  # Egyptian Franko
                
                if hasattr(self, 'workout_text'):
                    self.workout_text.delete("1.0", "end")
                    self.workout_text.insert("1.0", result)
                    self.workout_text.see("1.0")
                else:
                    print("mesh la2y el workout_text widget ya basha")  # Egyptian Franko
                
                self.save_workout_plan(result)
                
            except Exception as e:
                print(f"7asal error fel workout plan ya ray2: {str(e)}")  # Egyptian Franko
                self.show_error(f"Error processing workout plan: {str(e)}")
            finally:
                if hasattr(self, 'generate_button'):
                    self.generate_button.configure(state="normal")
        
        # Handle AI coach responses
        elif isinstance(result, str):
            if hasattr(self, 'chat_history'):
                self.chat_history.insert("end", f"AI Coach: {result}\n\n")
                self.chat_history.see("end")
                # Re-enable the ask button
                if hasattr(self, 'ask_button'):
                    self.ask_button.configure(state="normal")

    def save_workout_plan(self, plan):
        """Save the workout plan to file"""
        try:
            with open("workout_plan.json", "w") as f:
                json.dump({"plan": plan}, f)
        except Exception as e:
            self.show_error(f"Error saving workout plan: {str(e)}")

    def show_food_details(self, food_item):
        """Show detailed nutritional information for a food item"""
        dialog = ctk.CTkToplevel()
        dialog.title(f"Details: {food_item['food_name'].title()}")
        dialog.geometry("500x600")
        
        details_frame = ctk.CTkScrollableFrame(
            dialog,
            fg_color=("#2b2b2b", "#1a1a1a")
        )
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        try:
            image_url = food_item.get('photo', {}).get('thumb', None)
            if image_url:
                response = requests.get(image_url)
                img = Image.open(BytesIO(response.content))
                img = img.resize((100, 100), Image.Resampling.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 100))
                
                img_label = ctk.CTkLabel(
                    details_frame,
                    image=ctk_image,
                    text=""
                )
                img_label.pack(pady=10)
        except Exception as e:
            print(f"Error loading image: {e}")
        
        ctk.CTkLabel(
            details_frame,
            text=food_item['food_name'].title(),
            font=("Helvetica", 20, "bold")
        ).pack(pady=10)
        
        headers = {
            "x-app-id": NUTRITIONIX_APP_ID,
            "x-app-key": NUTRITIONIX_API_KEY,
            "x-remote-user-id": "0"
        }
        
        data = {
            "query": f"100g {food_item['food_name']}"
        }
        
        try:
            response = requests.post(
                "https://trackapi.nutritionix.com/v2/natural/nutrients",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'foods' in result and len(result['foods']) > 0:
                    food_data = result['foods'][0]
                    
                    info_items = [
                        ("Serving Size", "100g"),
                        ("Calories", f"{round(food_data.get('nf_calories', 0))} kcal"),
                        ("Protein", f"{round(food_data.get('nf_protein', 0))}g"),
                        ("Total Carbs", f"{round(food_data.get('nf_total_carbohydrate', 0))}g"),
                        ("Total Fat", f"{round(food_data.get('nf_total_fat', 0))}g"),
                        ("Saturated Fat", f"{round(food_data.get('nf_saturated_fat', 0))}g"),
                        ("Cholesterol", f"{round(food_data.get('nf_cholesterol', 0))}mg"),
                        ("Sodium", f"{round(food_data.get('nf_sodium', 0))}mg"),
                        ("Fiber", f"{round(food_data.get('nf_dietary_fiber', 0))}g"),
                        ("Sugars", f"{round(food_data.get('nf_sugars', 0))}g")
                    ]
                    
                    for label, value in info_items:
                        row = ctk.CTkFrame(
                            details_frame,
                            fg_color=("#333333", "#252525")
                        )
                        row.pack(fill="x", padx=10, pady=2)
                        
                        ctk.CTkLabel(
                            row,
                            text=label,
                            font=("Helvetica", 14)
                        ).pack(side="left", padx=10, pady=5)
                        
                        ctk.CTkLabel(
                            row,
                            text=value,
                            font=("Helvetica", 14, "bold")
                        ).pack(side="right", padx=10, pady=5)
                
        except Exception as e:
            self.show_error(f"Error fetching nutritional information: {str(e)}")

    def show_initial_setup(self):
        """Show initial setup window for new users"""
        setup_window = ctk.CTkToplevel()
        setup_window.title("Initial Setup")
        setup_window.geometry("500x600")
        
        setup_window.transient(self.window)
        setup_window.grab_set()
        
        setup_window.update_idletasks()
        width = setup_window.winfo_width()
        height = setup_window.winfo_height()
        x = (setup_window.winfo_screenwidth() // 2) - (width // 2)
        y = (setup_window.winfo_screenheight() // 2) - (height // 2)
        setup_window.geometry(f'+{x}+{y}')
        
        form_frame = ctk.CTkFrame(setup_window)
        form_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            form_frame,
            text="Welcome to AZ Workout!",
            font=("Helvetica", 24, "bold")
        ).pack(pady=20)
        
        fields = [
            ("Name", "name", "text"),
            ("Weight (kg)", "weight", "number"),
            ("Height (cm)", "height", "number"),
            ("Goal", "goal", ["Weight Loss", "Muscle Gain", "General Fitness"]),
            ("Activity Level", "activity_level", ["Sedentary", "Light", "Moderate", "Very Active", "Extra Active"])
        ]
        
        field_vars = {}
        
        for label, key, field_type in fields:
            field_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
            field_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(
                field_frame,
                text=label,
                font=("Helvetica", 14)
            ).pack(anchor="w")
            
            if field_type == "text" or field_type == "number":
                var = ctk.StringVar()
                field_vars[key] = var
                entry = ctk.CTkEntry(
                    field_frame,
                    textvariable=var,
                    font=("Helvetica", 14)
                )
                entry.pack(fill="x", pady=5)
            elif isinstance(field_type, list):
                var = ctk.StringVar(value=field_type[0])
                field_vars[key] = var
                for option in field_type:
                    ctk.CTkRadioButton(
                        field_frame,
                        text=option,
                        variable=var,
                        value=option,
                        font=("Helvetica", 14)
                    ).pack(side="left", padx=10)
        
        def save_profile():
            try:
                profile = {key: var.get() for key, var in field_vars.items()}
                
                if not all(profile.values()):
                    self.show_error("Please fill in all fields")
                    return
                
                with open("user_profile.json", "w") as f:
                    json.dump(profile, f)
                
                self.food_log = self.load_food_log()
                self.initialize_gemini()
                self.workout_plan = self.load_workout_plan()
                self.progress_data = self.load_progress_data()
                self.setup_gui()
                self.refresh_food_log()
                
                setup_window.destroy()
                
            except Exception as e:
                self.show_error(f"Error saving profile: {str(e)}")
        
        ctk.CTkButton(
            form_frame,
            text="Save & Continue",
            command=save_profile,
            font=("Helvetica", 14, "bold")
        ).pack(pady=20)

if __name__ == "__main__":
    app = AZFoodLogger()
    app.run()
        