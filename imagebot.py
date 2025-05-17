import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter, ImageDraw
import numpy as np
import os
import subprocess
import sys
import glob
import time
import threading
import requests
import shutil
import cv2
import random

# Global variables
PRESET_IMAGES_DIR = "preset_images"
TEMP_DIR = "temp"
IMG2IMG_TURBO_PATH = "C:/Users/dbmkr/Documents/AME 598 Minds and Machines/Module 6/Final Project - II/img2img-turbo-cpu/checkpoints"  # Update this with the path to img2img-turbo-cpu

# Sample images for presets
ART_SAMPLES = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/6/6a/Mona_Lisa.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Vincent_van_Gogh_-_Self-Portrait_-_Google_Art_Project_%28454045%29.jpg/1024px-Vincent_van_Gogh_-_Self-Portrait_-_Google_Art_Project_%28454045%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Meisje_met_de_parel.jpg/800px-Meisje_met_de_parel.jpg"
]

class DrawingCanvas(tk.Canvas):
    """Canvas for drawing sketches"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Drawing variables
        self.old_x = None
        self.old_y = None
        self.line_width = 2
        self.line_color = "black"
        self.eraser_mode = False
        
        # Bind events
        self.bind("<Button-1>", self.start_draw)
        self.bind("<B1-Motion>", self.draw)
        self.bind("<ButtonRelease-1>", self.stop_draw)
        
    
    def start_draw(self, event):
        self.old_x = event.x
        self.old_y = event.y
    
    def draw(self, event):
        if self.old_x and self.old_y:
            color = "white" if self.eraser_mode else self.line_color
            width = self.line_width * 3 if self.eraser_mode else self.line_width
            self.create_line(
                self.old_x, self.old_y, event.x, event.y,
                width=width, fill=color, capstyle=tk.ROUND, smooth=True
            )
        self.old_x = event.x
        self.old_y = event.y
    
    def stop_draw(self, event):
        self.old_x = None
        self.old_y = None
    
    def set_color(self, color):
        self.line_color = color
        self.eraser_mode = False
    
    def set_eraser(self):
        self.eraser_mode = True
    
    def set_line_width(self, width):
        self.line_width = int(width)
    
    def clear(self):
        self.delete("all")

class ImageBot:
    def __init__(self, root):
        self.root = root
        self.root.title("ImageBot")
        self.root.geometry("1200x800")
        
        # Create directories if they don't exist
        os.makedirs(PRESET_IMAGES_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs("outputs", exist_ok=True)
        
        # Initialize variables
        self.current_image = None
        self.original_image = None
        self.preset_selected = None
        self.preset_images = []
        self.stop_progress_animation = False

        # Setup UI
        self.setup_ui()
        
        # Load preset images
        self.load_preset_images()
        
        # Initialize chat with welcome message
        self.add_bot_message("👋 Welcome to ImageBot! I can help you edit images and create images from sketches.")
        self.add_bot_message("You can upload your own image, use a preset image, or create a sketch.")
        self.add_bot_message("Type 'help' to see what I can do.")
    
    def setup_ui(self):
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel for chat
        chat_frame = tk.Frame(main_frame, width=400, bg="#f0f0f0")
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Chat header
        chat_header = tk.Frame(chat_frame, bg="#4a7abc")
        chat_header.pack(fill=tk.X)
        
        tk.Label(chat_header, text="ImageBot Chat", font=("Arial", 14, "bold"), 
                 fg="white", bg="#4a7abc", pady=10).pack()
        
        # Chat display area with scrollbar
        chat_display_frame = tk.Frame(chat_frame)
        chat_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.chat_display = tk.Text(chat_display_frame, wrap=tk.WORD, state=tk.DISABLED, 
                                     bg="#f8f8f8", font=("Arial", 11))
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_display.tag_config("progress_base", foreground="#4a7abc")
        self.chat_display.tag_config("progress_dots", foreground="#4a7abc")
        
        scrollbar = tk.Scrollbar(chat_display_frame, command=self.chat_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.config(yscrollcommand=scrollbar.set)
        
        # Input area
        input_frame = tk.Frame(chat_frame, bg="#f0f0f0")
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.user_input = tk.Entry(input_frame, font=("Arial", 12))
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.user_input.bind("<Return>", self.send_message)
        
        send_button = tk.Button(input_frame, text="Send", bg="#4a7abc", fg="white",
                                command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Right panel for image display 
        image_frame = tk.Frame(main_frame, width=800, bg="#ffffff")
        image_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Image header
        image_header = tk.Frame(image_frame, bg="#4a7abc")
        image_header.pack(fill=tk.X)
        
        tk.Label(image_header, text="Image Editor", font=("Arial", 14, "bold"), 
                 fg="white", bg="#4a7abc", pady=10).pack()
        
        # Image display area
        self.image_display = tk.Label(image_frame, bg="#f0f0f0", text="No image loaded")
        self.image_display.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Control buttons
        control_frame = tk.Frame(image_frame, bg="#ffffff")
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Main action buttons
        button_frame = tk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(button_frame, text="Load Image", bg="#4a7abc", fg="white", 
                 command=self.upload_image).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Use Preset Image", bg="#4a7abc", fg="white",
                 command=self.show_preset_dialog).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Create Sketch", bg="#4a7abc", fg="white",
                 command=self.show_sketch_dialog).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Reset Image", bg="#4a7abc", fg="white",
                 command=self.reset_image).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Save Image", bg="#4a7abc", fg="white",
                 command=self.save_image).pack(side=tk.LEFT, padx=5)
    
    def add_bot_message(self, message):
        """Add a message from the bot to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, "🤖 Bot: " + message + "\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def add_user_message(self, message):
        """Add a user message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, "👤 You: " + message + "\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def send_message(self, event=None):
        """Process user message when sent"""
        message = self.user_input.get().strip()
        if message:
            self.add_user_message(message)
            self.user_input.delete(0, tk.END)
            
            # Process message and respond
            self.process_message(message)
    
    def process_message(self, message):
        """Process user message and determine response"""
        message_lower = message.lower()
        
        # Check for exit/quit command
        if any(word in message_lower for word in ["exit", "quit", "close"]):
            self.add_bot_message("Closing the application. Goodbye!")
            self.root.after(1500, self.root.destroy)  # Close after 1.5 seconds
            return
            
        # Enhanced command processing with more context awareness
        
        # Reset image
        if "reset" in message_lower:
            if self.current_image:
                self.reset_image()
            else:
                self.add_bot_message("No image to reset.")
            return
            
        # Save image
        if "save" in message_lower:
            if self.current_image:
                self.save_image()
            else:
                self.add_bot_message("No image to save.")
            return
            
        # Load image
        if any(word in message_lower for word in ["load", "upload", "open"]):
            self.upload_image()
            return
            
        # Preset images
        if any(word in message_lower for word in ["preset", "example"]):
            self.show_preset_dialog()
            return
        
        # Check for image editing commands
        if self.current_image:
            # Apply edge detection
            if any(word in message_lower for word in ["edge", "outline", "detect edges"]):
                self.apply_edge_detection()
                return
                
            # Apply blur
            if "blur" in message_lower:
                self.apply_blur()
                return
                
            # Convert to grayscale
            if any(word in message_lower for word in ["gray", "grayscale", "black and white"]):
                self.apply_grayscale()
                return
                
            # Brightness adjustments
            if "bright" in message_lower:
                if any(word in message_lower for word in ["increase", "more", "+"]):
                    self.adjust_brightness(1.1)  # Increase by 10%
                    return
                elif any(word in message_lower for word in ["decrease", "less", "-"]):
                    self.adjust_brightness(0.9)  # Decrease by 10%
                    return
                    
            # Contrast adjustments
            if "contrast" in message_lower:
                if any(word in message_lower for word in ["increase", "more", "+"]):
                    self.adjust_contrast(1.1)  # Increase by 10%
                    return
                elif any(word in message_lower for word in ["decrease", "less", "-"]):
                    self.adjust_contrast(0.9)  # Decrease by 10%
                    return
        
        # Sketch commands
        if any(word in message_lower for word in ["sketch", "drawing", "draw"]):
            self.add_bot_message("Let's create a sketch and transform it into an image!")
            threading.Timer(1.0, self.show_sketch_dialog).start()
            return
            
        # Help command
        if "help" in message_lower:
            self.add_bot_message("I can help you with image editing and creating images from sketches. Here's what I can do:")
            self.add_bot_message("1. Load your own image or use an example image")
            self.add_bot_message("2. Create a sketch and transform it into an image using AI")
            self.add_bot_message("3. Apply adjustments: brightness, contrast, grayscale, edge detection, blur")
            self.add_bot_message("4. Reset an image to its original state - keyword: 'reset'")
            self.add_bot_message("5. Save your edited image")
            self.add_bot_message("6. Type 'exit' or 'quit' to close the application")
            self.add_bot_message("Just tell me what you'd like to do!")
            return
            
        # If no specific command was recognized
        self.add_bot_message("I'm not sure what you're asking for. Type 'help' to see what I can do.")
    
    def load_preset_images(self):
        """Load or download preset images"""
        print("Loading preset images...")
        
        # Check if we have existing images
        existing_files = [f for f in os.listdir(PRESET_IMAGES_DIR) 
                        if f.endswith(('.jpg', '.jpeg', '.png')) and os.path.isfile(os.path.join(PRESET_IMAGES_DIR, f))]
        
        # If we don't have enough images, try to download them
        if len(existing_files) < 4:
            print("Downloading preset images. Please wait...")
            
            successful_downloads = 0
            for i, url in enumerate(ART_SAMPLES):
                try:
                    # Use a more robust download method
                    img_path = os.path.join(PRESET_IMAGES_DIR, f"preset_{i+1}.jpg")
                    
                    # Create a session with timeout and headers
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': 'Chrome/91.0.4472.124 Safari/537.36'
                    })
                    
                    # Download with timeout
                    response = session.get(url, timeout=10)
                    if response.status_code == 200:
                        with open(img_path, 'wb') as f:
                            f.write(response.content)
                        self.preset_images.append(img_path)
                        successful_downloads += 1
                        print(f"Downloaded image {i+1} to {img_path}")
                    else:
                        print(f"Failed to download image {i+1}: HTTP status {response.status_code}")
                except Exception as e:
                    print(f"Error downloading image {i+1}: {e}")
            
            if successful_downloads == 0:
                # If all downloads failed, try to create placeholder images
                print("Could not download preset images. Creating placeholders...")
                try:
                    # Create 4 different colored placeholder images
                    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
                    
                    for i, color in enumerate(colors):
                        img = Image.new('RGB', (300, 300), color=color)
                        draw = ImageDraw.Draw(img)
                        
                        img_path = os.path.join(PRESET_IMAGES_DIR, f"preset_{i+1}.jpg")
                        img.save(img_path)
                        self.preset_images.append(img_path)
                        print(f"Created placeholder image {i+1}")
                except Exception as e:
                    print(f"Error creating placeholder images: {e}")
        else:
            # Use existing files
            for file in sorted(existing_files)[:4]:
                full_path = os.path.join(PRESET_IMAGES_DIR, file)
                self.preset_images.append(full_path)
                print(f"Found existing image: {full_path}")
    
    def show_preset_dialog(self):
        """Show dialog with preset images for selection"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Preset Image")
        dialog.geometry("800x600")
        
        frame = tk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Add instructions label
        tk.Label(dialog, text="Click on an image to select it", 
                font=("Arial", 12), pady=10).pack()
                
        # Save references to images to prevent garbage collection
        self.preset_image_refs = []
        
        for i, img_path in enumerate(self.preset_images):
            try:
                img = Image.open(img_path)
                img.thumbnail((150, 150))
                photo = ImageTk.PhotoImage(img)
                self.preset_image_refs.append(photo)  # Prevent garbage collection
                
                # Create frame for each image with label
                img_frame = tk.Frame(frame, borderwidth=2, relief="ridge")
                img_frame.grid(row=i//2, column=i%2, padx=10, pady=10, sticky="nsew")
                
                # Image
                label = tk.Label(img_frame, image=photo, cursor="hand2")
                label.image = photo  # Keep a reference
                label.pack(padx=5, pady=5)
                
                # Caption
                caption = tk.Label(img_frame, text=f"Preset {i+1}", font=("Arial", 10, "bold"))
                caption.pack(pady=5)
                
                # Bind click events
                label.bind("<Button-1>", lambda e, path=img_path: self.select_preset_image(path, dialog))
                caption.bind("<Button-1>", lambda e, path=img_path: self.select_preset_image(path, dialog))
                img_frame.bind("<Button-1>", lambda e, path=img_path: self.select_preset_image(path, dialog))
            except Exception as e:
                print(f"Error loading preset image {i}: {e}")
        
        # Set grid weights to make the cells expand properly
        for i in range(2):  # 2 columns
            frame.grid_columnconfigure(i, weight=1)
    
    def select_preset_image(self, img_path, dialog):
        """Handle preset image selection"""
        try:
            img = Image.open(img_path)
            self.original_image = img.copy()
            self.current_image = img.copy()
            self.preset_selected = img_path
            self.display_image(self.current_image)
            self.add_bot_message(f"Preset image selected! What would you like to do with it?")
            dialog.destroy()
        except Exception as e:
            self.add_bot_message(f"Error selecting image: {e}")
            dialog.destroy()
    
    def upload_image(self):
        """Allow user to upload an image"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif")]
        )
        if file_path:
            try:
                img = Image.open(file_path)
                self.original_image = img.copy()
                self.current_image = img.copy()
                self.display_image(self.current_image)
                self.add_bot_message(f"Image uploaded successfully! What would you like to do with it?")
            except Exception as e:
                self.add_bot_message(f"Error opening image: {e}")
    
    def display_image(self, img):
        """Display the current image in the UI"""
        try:
            if img is None:
                print("Warning: Attempted to display None image")
                return
                
            # Create a copy to avoid modifying the original
            img_copy = img.copy()
            
            # Resize the image to fit the display area while maintaining aspect ratio
            max_width, max_height = 700, 500
            img_copy.thumbnail((max_width, max_height))
            
            # Convert to RGB if needed
            if img_copy.mode != 'RGB':
                img_copy = img_copy.convert('RGB')
            
            # Create new PhotoImage
            photo = ImageTk.PhotoImage(img_copy)
            
            # Store reference 
            self.current_photo = photo
            
            # Update the display
            self.image_display.config(image=photo)
            
            # Force update
            self.root.update_idletasks()
            
        except Exception as e:
            print(f"Error displaying image: {e}")
    
    def reset_image(self):
        """Reset to the original image"""
        if self.original_image:
            self.current_image = self.original_image.copy()
            self.display_image(self.current_image)
            self.add_bot_message("Image has been reset to original.")
        else:
            self.add_bot_message("No original image to restore.")
    
    def save_image(self):
        """Save the current image locally"""
        if self.current_image:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    self.current_image.save(file_path)
                    self.add_bot_message(f"Image saved successfully!")
                except Exception as e:
                    self.add_bot_message(f"Error saving image: {e}")
        else:
            self.add_bot_message("No image to save.")
    
    def apply_grayscale(self):
        """Convert image to grayscale"""
        if self.current_image:
            self.current_image = ImageOps.grayscale(self.current_image).convert("RGB")
            self.display_image(self.current_image)
            self.add_bot_message("Grayscale filter applied.")
        else:
            self.add_bot_message("No image loaded.")
    
    def adjust_brightness(self, factor):
        """Adjust image brightness by a factor"""
        if self.current_image:
            try:
                # Convert to a format that supports these operations if needed
                if self.current_image.mode != 'RGB':
                    img = self.current_image.convert('RGB')
                else:
                    img = self.current_image.copy()
                    
                enhancer = ImageEnhance.Brightness(img)
                self.current_image = enhancer.enhance(factor)
                self.display_image(self.current_image)
                self.add_bot_message(f"Brightness adjusted by {int((factor-1)*100)}%.")
            except Exception as e:
                self.add_bot_message(f"Error adjusting brightness: {e}")
        else:
            self.add_bot_message("No image loaded.")
    
    def adjust_contrast(self, factor):
        """Adjust image contrast by a factor"""
        if self.current_image:
            try:
                # Convert to a format that supports these operations if needed
                if self.current_image.mode != 'RGB':
                    img = self.current_image.convert('RGB')
                else:
                    img = self.current_image.copy()
                    
                enhancer = ImageEnhance.Contrast(img)
                self.current_image = enhancer.enhance(factor)
                self.display_image(self.current_image)
                self.add_bot_message(f"Contrast adjusted by {int((factor-1)*100)}%.")
            except Exception as e:
                self.add_bot_message(f"Error adjusting contrast: {e}")
        else:
            self.add_bot_message("No image loaded.")

    def apply_edge_detection(self):
        """Apply edge detection to image"""
        if self.current_image:
            try:
                # Convert to numpy array for processing
                img_array = np.array(self.current_image)
                
                # Convert to grayscale if it's not already
                if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                    gray_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                else:
                    gray_img = img_array
                
                # Apply Canny edge detection
                edges = cv2.Canny(gray_img, 100, 200)
                
                # Convert back to PIL
                self.current_image = Image.fromarray(edges).convert("RGB")
                self.display_image(self.current_image)
                self.add_bot_message("Edge detection applied.")
            except Exception as e:
                self.add_bot_message(f"Error applying edge detection: {e}")
        else:
            self.add_bot_message("No image loaded.")
    
    def apply_blur(self):
        """Apply Gaussian blur to image"""
        if self.current_image:
            try:
                self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=3))
                self.display_image(self.current_image)
                self.add_bot_message("Blur filter applied.")
            except Exception as e:
                self.add_bot_message(f"Error applying blur: {e}")
        else:
            self.add_bot_message("No image loaded.")

    def show_sketch_dialog(self):
        """Show a dialog for sketching and generating an image"""
        # Create a new toplevel window
        sketch_dialog = tk.Toplevel(self.root)
        sketch_dialog.title("Sketch and Generate")
        sketch_dialog.geometry("800x700")
        
        # Create frame for canvas
        canvas_frame = tk.Frame(sketch_dialog)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create canvas for drawing
        canvas = DrawingCanvas(canvas_frame, bg="white", width=700, height=500)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Control panel - simplified
        control_panel = tk.Frame(sketch_dialog)
        control_panel.pack(fill=tk.X, padx=10, pady=5)
        
        # Eraser button
        eraser_btn = tk.Button(control_panel, text="Eraser", command=canvas.set_eraser)
        eraser_btn.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        clear_btn = tk.Button(control_panel, text="Clear Canvas", command=canvas.clear)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Prompt input
        prompt_frame = tk.Frame(sketch_dialog)
        prompt_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(prompt_frame, text="Prompt:").pack(side=tk.LEFT)
        prompt_entry = tk.Entry(prompt_frame, width=50)
        prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        prompt_entry.insert(0, "A colorful scene")
        
        # Generate and button frame
        button_frame = tk.Frame(sketch_dialog)
        button_frame.pack(pady=10)
        
        def generate_image():
            # Get the prompt
            prompt = prompt_entry.get()
            if not prompt:
                messagebox.showwarning("Warning", "Please enter a prompt")
                return
            
            # Save the canvas as an image
            os.makedirs(TEMP_DIR, exist_ok=True)
            temp_file = os.path.join(TEMP_DIR, f"sketch_{int(time.time())}.png")
            
            if self.save_canvas_as_image(canvas, temp_file):
                # Process the sketch
                self.process_sketch_to_image(temp_file, prompt)
                
                # Close the dialog
                sketch_dialog.destroy()
        
        # Generate button
        generate_btn = tk.Button(button_frame, text="Generate Image", bg="#ff9900", fg="white", 
                            command=generate_image)
        generate_btn.pack(side=tk.LEFT, padx=10)
        
        # Reset button
        reset_btn = tk.Button(button_frame, text="Reset", 
                            command=canvas.clear)
        reset_btn.pack(side=tk.LEFT, padx=10)
        
        # Cancel button
        cancel_btn = tk.Button(button_frame, text="Cancel", 
                            command=sketch_dialog.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)
    
    def save_canvas_as_image(self, canvas, filename):
        """Save the canvas as an image file"""
        try:
            # Get canvas dimensions
            width = canvas.winfo_width()
            height = canvas.winfo_height()
            
            # Create a new image with white background
            image = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(image)
            
            # Draw all items from the canvas directly to the image
            for item in canvas.find_all():
                if canvas.type(item) == "line":
                    # Get line coordinates
                    coords = canvas.coords(item)
                    # Get line color and width
                    color = canvas.itemcget(item, "fill")
                    width_val = float(canvas.itemcget(item, "width"))
                    
                    # Draw line on image
                    if len(coords) >= 4:  # Line has at least two points (x1,y1,x2,y2)
                        for i in range(0, len(coords) - 2, 2):
                            draw.line(
                                (coords[i], coords[i+1], coords[i+2], coords[i+3]),
                                fill=color, 
                                width=int(width_val)
                            )
            
            # Save the image
            image.save(filename)
            self.add_bot_message(f"Sketch saved")
            return True
            
        except Exception as e:
            print(f"Error saving canvas: {e}")
            # Fallback method - try screenshot method
            try:
                # For Windows
                if sys.platform.startswith('win'):
                    from PIL import ImageGrab
                    x = canvas.winfo_rootx() + canvas.winfo_x()
                    y = canvas.winfo_rooty() + canvas.winfo_y()
                    width = canvas.winfo_width()
                    height = canvas.winfo_height()
                    image = ImageGrab.grab(bbox=(x, y, x+width, y+height))
                    image.save(filename)
                    self.add_bot_message(f"Sketch saved")
                    return True
            except Exception as sub_error:
                print(f"Fallback error: {sub_error}")
                messagebox.showerror("Error", f"Could not save sketch: {e}")
                return False
            
            return False
    
    def process_sketch_to_image(self, sketch_path, prompt):
        """Process the sketch and generate an image"""
        self.add_bot_message(f"Generating image from sketch with prompt: '{prompt}'...")
        
        # Make sure the output directory exists
        os.makedirs("outputs", exist_ok=True)
        
        # Set the correct path to the img2img-turbo directory
        img2img_path = "C:\\Users\\dbmkr\\Documents\\AME 598 Minds and Machines\\Module 6\\Final Project - II\\img2img-turbo-cpu"
        random_gamma = round(random.uniform(0.5, 0.7), 1)  # Round to 1 decimal place
        random_seed = random.randint(1, 10000) # random seed for reproducibility

        # Copy the sketch file to the img2img-turbo directory to avoid path issues
        sketch_filename = os.path.basename(sketch_path)
        img2img_sketch_path = os.path.join(img2img_path, sketch_filename)
        
        try:
            # Copy the sketch file to the img2img-turbo directory
            shutil.copy(sketch_path, img2img_sketch_path)
            self.add_bot_message(f"Copied sketch for processing.")
        except Exception as e:
            self.add_bot_message(f"Error copying sketch file: {e}")
            return
        
        # Get virtual environment Python path
        venv_python = os.path.join(img2img_path, "venv", "Scripts", "python.exe")
        if not os.path.exists(venv_python):
            venv_python = sys.executable
        
        # Create the command with the local path to the sketch file
        cmd = [
            venv_python,
            "src/inference_paired.py",
            "--model_name", "sketch_to_image_stochastic",
            "--input_image", sketch_filename,
            "--gamma", str(random_gamma),  # Convert to string
            "--seed", str(random_seed),    # Add seed parameter
            "--prompt", prompt,
            "--output_dir", "outputs"
        ]
        
        try:
            # Start showing progress animation - ADD THIS LINE
            self.show_progress_animation("Generating image", 60)  # Animation for up to 30 seconds
            
            # Important: Run the process from the img2img-turbo directory
            process = subprocess.Popen(
                cmd, 
                cwd=img2img_path,  # Set the working directory to img2img-turbo folder
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            def check_process():
                if process.poll() is None:
                    # Process still running
                    self.root.after(1000, check_process)
                else:
                    # Process completed
                    # Stop the progress animation - ADD THIS LINE
                    self.stop_progress_animation = True
                    
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        self.add_bot_message(f"Error generating image: {stderr}")
                        return
                    
                    # Find the latest generated image
                    output_dir = os.path.join(img2img_path, "outputs")
                    generated_files = glob.glob(os.path.join(output_dir, "*.png"))
                    if not generated_files:
                        self.add_bot_message("No output image was generated.")
                        return
                    
                    # Get the most recent file
                    latest_file = max(generated_files, key=os.path.getctime)
                    
                    # Load and display the generated image
                    generated_img = Image.open(latest_file)
                    self.original_image = generated_img.copy()
                    self.current_image = generated_img.copy()
                    self.display_image(self.current_image)
                    
                    self.add_bot_message(f"Image generated successfully! To save image type save.")
                    
                    # Clean up the temporary sketch file
                    try:
                        os.remove(img2img_sketch_path)
                    except:
                        pass
            
            # Start checking process status
            check_process()
                
        except Exception as e:
            # Stop the progress animation if there's an error - ADD THIS LINE
            self.stop_progress_animation = True
            
            self.add_bot_message(f"Error processing sketch: {str(e)}")
            print(f"Error details: {str(e)}")
    
    def show_progress_animation(self, message, seconds):
        """Show a progress animation in the chat"""
        # Add the initial message with a special tag
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"🤖 Bot: {message} ", "progress_base")
        animation_pos = self.chat_display.index(tk.END + "-1c")  # Get position for animation
        self.chat_display.insert(tk.END, "   \n\n", "progress_dots")  # Space for dots
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        
        # Define the animation function
        def animate():
            self.stop_progress_animation = False
            animation = [".  ", ".. ", "..."]
            for _ in range(seconds * 2):  # Update every 0.5 seconds
                if self.stop_progress_animation:
                    break
                for frame in animation:
                    if self.stop_progress_animation:
                        break
                    # Update just the dots part
                    self.chat_display.config(state=tk.NORMAL)
                    self.chat_display.delete(animation_pos, animation_pos + "+3c")  # Delete previous dots
                    self.chat_display.insert(animation_pos, frame)  # Insert new dots
                    self.chat_display.config(state=tk.DISABLED)
                    self.chat_display.see(tk.END)
                    time.sleep(0.5)

        # Run the animation in a separate thread
        threading.Thread(target=animate, daemon=True).start()
    

# Main application entry point
def main():
    root = tk.Tk()
    app = ImageBot(root)
    root.mainloop()

if __name__ == "__main__":
    main()