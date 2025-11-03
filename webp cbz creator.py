#!/usr/bin/env python3
"""
Advanced WebP + CBZ Converter (Simplified GUI)
- Replaces file dialogs and DND with a multi-line path input.
- Combines file, folder, and CBZ processing into a single 'Process' action.
- FIXES: Guarantees per-picture GUI updates for smoother progress bars.
- NEW: Added Resize longest size option with Lanczos downscaling.
"""

import os
import json
import shutil
import tempfile
import zipfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext # Added scrolledtext
from PIL import Image
from datetime import datetime
from collections import namedtuple
from typing import List, Callable, Optional
import queue 

# Removed TkinterDnD dependency

# ----------------------------------------------------------------------
# Constants & Types
# ----------------------------------------------------------------------
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif', '.avif')
CONFIG_FILE = os.path.expanduser("~/.webp_converter_config.json")
Result = namedtuple('Result', 'success message path')

# ----------------------------------------------------------------------
# GUI Helper Functions (Copied/Adapted from cbz creator)
# ----------------------------------------------------------------------
def get_paths_from_input(text_widget, root_window):
    """Extracts and cleans paths from the text widget, checking for existence."""
    raw_paths = text_widget.get("1.0", tk.END).strip().split('\n')
    
    cleaned_paths = [
        p.strip().strip('"').strip("'").replace('\r', '') 
        for p in raw_paths 
        if p.strip()
    ]
    
    existing_paths = [p for p in cleaned_paths if os.path.exists(p)]
    
    non_existent_paths = [p for p in cleaned_paths if not os.path.exists(p)]
    if non_existent_paths:
        # Use root_window for messagebox to ensure it's on top of the main app
        messagebox.showwarning("Missing Paths", 
                              f"The following paths could not be found and were ignored:\n" + 
                              "\n".join(non_existent_paths[:5]) + 
                              ("\n..." if len(non_existent_paths) > 5 else ""),
                              parent=root_window)
        
    return existing_paths

def paste_paths(text_widget, root_window):
    """Handles paste functionality with path parsing."""
    try:
        clipboard_content = root_window.clipboard_get()
        paths = [line.strip() for line in clipboard_content.split('\n') if line.strip()]
        cleaned_paths = [p.strip('"').strip("'") for p in paths]
        
        current_content = text_widget.get("1.0", tk.END).strip()
        
        if current_content:
            text_widget.insert(tk.END, "\n" + "\n".join(cleaned_paths))
        else:
            text_widget.insert(tk.END, "\n".join(cleaned_paths))
            
    except tk.TclError:
        messagebox.showinfo("Paste", "No text data found in clipboard.", parent=root_window)

def clear_input(text_widget):
    """Clears the input text area."""
    text_widget.delete("1.0", tk.END)


# ----------------------------------------------------------------------
# Config Management (Unchanged)
# ----------------------------------------------------------------------
class Config:
    def __init__(self):
        self.quality = 90
        self.lossless = False
        self.save_as_cbz = False
        self.webp_method = 4
        self.resize_enabled = False
        self.max_size = 1920
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.quality = data.get("quality", 90)
                    self.lossless = data.get("lossless", False)
                    self.save_as_cbz = data.get("save_as_cbz", False)
                    self.webp_method = data.get("webp_method", 4)
                    self.resize_enabled = data.get("resize_enabled", False)
                    self.max_size = data.get("max_size", 1920)
            except Exception:
                pass

    def save(self):
        data = {
            "quality": self.quality,
            "lossless": self.lossless,
            "save_as_cbz": self.save_as_cbz,
            "webp_method": self.webp_method,
            "resize_enabled": self.resize_enabled,
            "max_size": self.max_size
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

# ----------------------------------------------------------------------
# Core Conversion (Unchanged - except for being inside the class)
# ----------------------------------------------------------------------
def convert_image_to_webp(file_path: str, output_dir: str, config: Config) -> Result:
    try:
        img = Image.open(file_path)

        if 'A' in img.getbands() or img.mode == 'P':
            img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # --- RESIZE LOGIC ---
        if config.resize_enabled and config.max_size > 0:
            width, height = img.size
            longest_side = max(width, height)
            
            if longest_side > config.max_size:
                ratio = config.max_size / longest_side
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                resize_msg = f"Resized from {width}x{height} to {new_width}x{new_height}"
            else:
                resize_msg = ""
        else:
            resize_msg = ""
        # --- END RESIZE LOGIC ---


        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}.webp")

        img.save(
            output_path, 
            "WEBP", 
            quality=config.quality, 
            lossless=config.lossless, 
            method=config.webp_method
        )
        
        message = f"Converted: {os.path.basename(file_path)}"
        if resize_msg:
            message += f" ({resize_msg})"

        return Result(True, message, output_path)
    except Exception as e:
        return Result(False, f"Error: {os.path.basename(file_path)} → {e}", None)

def count_images_in_path(path: str) -> int:
    if os.path.isfile(path):
        return 1 if path.lower().endswith(IMAGE_EXTS) else 0
    return len([f for f in os.listdir(path) if f.lower().endswith(IMAGE_EXTS)])

def quick_scan_cbz_image_count(cbz_path):
    try:
        with zipfile.ZipFile(cbz_path, 'r') as zf:
            return len([name for name in zf.namelist() if name.lower().endswith(IMAGE_EXTS)])
    except Exception:
        return 50 # Default estimate on failure
        
# ----------------------------------------------------------------------
# Worker Thread Logic (Unchanged)
# ----------------------------------------------------------------------
# (ConversionWorker, process_files, process_folders, process_single_folder,
# process_cbz_archives, process_single_cbz are all left as-is from v2, 
# as they handle the core logic fine)

class ConversionWorker(threading.Thread):
# ... (All methods of ConversionWorker are unchanged from the original v2 file)
# To save space, the full body of ConversionWorker is omitted here, but it remains identical.
# ----------------------------------------------------------------------
# (Skipping the unchanged ConversionWorker class body for brevity)
# ----------------------------------------------------------------------
    def __init__(self, tasks, config: Config, update_queue: queue.Queue):
        super().__init__(daemon=True)
        self.tasks = tasks
        self.config = config
        self.update_queue = update_queue
        self.cancelled = threading.Event()
        self.log_lines = []
        self.completed = 0 

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        self.log_lines.append(line)

    def post_update(self, kind, msg=None, total=None):
        self.update_queue.put({'kind': kind, 'msg': msg, 'done': self.completed, 'total': total})

    def run(self):
        total = sum(task['count'] for task in self.tasks)
        
        self.post_update("update", "Starting conversion...", total=total)

        for task in self.tasks:
            if self.cancelled.is_set():
                self.post_update("cancelled")
                return

            kind = task['kind']
            paths = task['paths']

            if kind == "files":
                self.process_files(paths, total)
            elif kind == "folders":
                self.process_folders(paths, total)
            elif kind == "cbz":
                self.process_cbz_archives(paths, total)
            
            if self.cancelled.is_set():
                self.post_update("cancelled")
                return

        self.post_update("done", self.log_lines)

    def process_files(self, filepaths: List[str], total: int) -> List[Result]:
        results = []
        dir_groups = {}
        for fp in filepaths:
            parent_dir = os.path.dirname(fp)
            if parent_dir not in dir_groups:
                dir_groups[parent_dir] = []
            dir_groups[parent_dir].append(fp)

        for parent_dir, files in dir_groups.items():
            if self.cancelled.is_set(): break
            
            output_dir = os.path.join(parent_dir, "_webp_converted")
            os.makedirs(output_dir, exist_ok=True)
            
            for fp in files:
                if self.cancelled.is_set(): break
                result = convert_image_to_webp(fp, output_dir, self.config)
                results.append(result)
                self.log(result.message)
                
                # Per-image update
                self.completed += 1
                self.post_update("update", result.message, total)
                
            if not self.cancelled.is_set():
                finish_result = Result(True, f"Files saved to: {os.path.basename(output_dir)}", output_dir)
                results.append(finish_result)
                self.log(finish_result.message)
                self.post_update("update", finish_result.message, total)
                
        return results

    def process_folders(self, folderpaths: List[str], total: int) -> List[Result]:
        results = []
        for folder in folderpaths:
            if self.cancelled.is_set(): break
            results.extend(self.process_single_folder(folder, total))
        return results

    def process_single_folder(self, folder_path: str, total: int) -> List[Result]:
        results = []
        temp_dir = tempfile.mkdtemp()
        image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                       if f.lower().endswith(IMAGE_EXTS)]

        # Convert
        for fp in image_files:
            if self.cancelled.is_set(): break
            r = convert_image_to_webp(fp, temp_dir, self.config) 
            results.append(r)
            self.log(r.message)
            
            # Per-image update
            self.completed += 1
            self.post_update("update", r.message, total)


        # Output (only if conversion wasn't cancelled mid-way)
        if not self.cancelled.is_set():
            base_name = os.path.basename(folder_path).rstrip('.cbz')
            output_dir = os.path.dirname(folder_path)

            if self.config.save_as_cbz:
                cbz_name = f"{base_name}_webp.cbz"
                cbz_path = os.path.join(output_dir, cbz_name)
                try:
                    with zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for item in os.listdir(temp_dir):
                            zf.write(os.path.join(temp_dir, item), item)
                    finish_result = Result(True, f"CBZ created: {cbz_name}", cbz_path)
                    results.append(finish_result)
                except Exception as e:
                    finish_result = Result(False, f"CBZ creation error: {e}", None)
                    results.append(finish_result)
            else:
                out_folder = os.path.join(output_dir, f"{base_name}_webp")
                os.makedirs(out_folder, exist_ok=True)
                for item in os.listdir(temp_dir):
                    shutil.move(os.path.join(temp_dir, item), os.path.join(out_folder, item))
                finish_result = Result(True, f"Folder saved: {os.path.basename(out_folder)}", out_folder)
                results.append(finish_result)

            self.log(finish_result.message)
            self.post_update("update", finish_result.message, total)


        shutil.rmtree(temp_dir, ignore_errors=True)
        return results

    def process_cbz_archives(self, cbz_paths: List[str], total: int) -> List[Result]:
        results = []
        for cbz_path in cbz_paths:
            if self.cancelled.is_set(): break
            results.extend(self.process_single_cbz(cbz_path, total))
        return results

    def process_single_cbz(self, cbz_path: str, total: int) -> List[Result]:
        results = []
        extract_dir = tempfile.mkdtemp()
        convert_dir = tempfile.mkdtemp()

        try:
            # 1. Extract
            with zipfile.ZipFile(cbz_path, 'r') as zf:
                zf.extractall(extract_dir)

            image_files = [os.path.join(extract_dir, f) for f in os.listdir(extract_dir)
                           if f.lower().endswith(IMAGE_EXTS)]

            # 2. Convert
            for fp in image_files:
                if self.cancelled.is_set(): break
                r = convert_image_to_webp(fp, convert_dir, self.config) 
                results.append(r)
                self.log(r.message)
                
                # Per-image update
                self.completed += 1
                self.post_update("update", r.message, total)


            # 3. Re-zip (only if conversion wasn't cancelled mid-way)
            if not self.cancelled.is_set():
                base_name = os.path.splitext(os.path.basename(cbz_path))[0]
                output_cbz = os.path.join(os.path.dirname(cbz_path), f"{base_name}_webp.cbz")
                with zipfile.ZipFile(output_cbz, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for item in os.listdir(convert_dir):
                        zf.write(os.path.join(convert_dir, item), item)

                finish_result = Result(True, f"New CBZ: {os.path.basename(output_cbz)}", output_cbz)
                results.append(finish_result)
                self.log(finish_result.message)
                self.post_update("update", finish_result.message, total)


        except Exception as e:
            error_result = Result(False, f"CBZ error: {e}", None)
            results.append(error_result)
            self.log(error_result.message)
            self.post_update("update", error_result.message, total)
            
            # Since the CBZ failed, we must still account for its image count to keep the total accurate
            self.completed += len(image_files) - sum(1 for r in results if r.success)
            self.post_update("update", f"Adjusted counter after failure.", total)

        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)
            shutil.rmtree(convert_dir, ignore_errors=True)

        return results


# ----------------------------------------------------------------------
# GUI Application
# ----------------------------------------------------------------------
class WebPConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Advanced WebP + CBZ Converter")
        master.geometry("560x520") # Adjusted size for input box
        master.minsize(500, 400)

        self.config = Config()
        self.worker = None
        self.progress_window = None
        self.update_queue = queue.Queue()
        self.input_text = None # Will be set in setup_ui

        self.setup_ui()
        self.load_config_into_ui()
        self.master.after(100, self.check_queue)
        
    def setup_ui(self):
        main = ttk.Frame(self.master, padding=15)
        main.pack(fill='both', expand=True)

        # === Quality & Options (Unchanged) ===
        opts = ttk.LabelFrame(main, text=" Conversion Settings ")
        opts.pack(fill='x', pady=10)
        
        opts.columnconfigure(0, weight=1)
        opts.columnconfigure(1, weight=0)
        opts.columnconfigure(2, weight=1)
        opts.columnconfigure(3, weight=1)

        # Row 0: Quality and Lossless
        ttk.Label(opts, text="Quality (0-100):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.quality_var = tk.StringVar()
        quality_entry = ttk.Entry(opts, textvariable=self.quality_var, width=6)
        quality_entry.grid(row=0, column=1, padx=5, pady=5)
        quality_entry.bind('<FocusOut>', lambda e: self.validate_quality())

        self.lossless_var = tk.BooleanVar()
        ttk.Checkbutton(opts, text="Lossless WebP", variable=self.lossless_var).grid(row=0, column=2, padx=20, sticky='w')
        
        # Row 1: CBZ Save
        self.cbz_var = tk.BooleanVar()
        cbz_cb = ttk.Checkbutton(opts, text="Save folders as .cbz", variable=self.cbz_var)
        cbz_cb.grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=5)
        
        # Row 2: WebP Effort Method (1-6)
        ttk.Label(opts, text="WebP Effort (1-6):").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.method_var = tk.StringVar()
        method_entry = ttk.Entry(opts, textvariable=self.method_var, width=6)
        method_entry.grid(row=2, column=1, padx=5, pady=5)
        method_entry.bind('<FocusOut>', lambda e: self.validate_method())
        ttk.Label(opts, text="(6=Slowest/Best, 1=Fastest/Good)").grid(row=2, column=2, sticky='w', columnspan=2)

        # Row 3: RESIZE OPTION
        self.resize_var = tk.BooleanVar()
        resize_cb = ttk.Checkbutton(opts, text="Resize longest side [", variable=self.resize_var)
        resize_cb.grid(row=3, column=0, sticky='w', padx=5, pady=5)
        
        self.max_size_var = tk.StringVar()
        max_size_entry = ttk.Entry(opts, textvariable=self.max_size_var, width=6)
        max_size_entry.grid(row=3, column=1, padx=0, pady=5, sticky='w')
        max_size_entry.bind('<FocusOut>', lambda e: self.validate_max_size())
        
        ttk.Label(opts, text="] px").grid(row=3, column=2, sticky='w')


        # === Input Area (REPLACES action buttons and DND) ===
        ttk.Label(
            main, 
            text="Paste File/Folder/CBZ Paths below (one per line) or use the Paste button:",
            font=('Arial', 10, 'bold')
        ).pack(pady=(10,5), padx=10, anchor='w')
        
        self.input_text = scrolledtext.ScrolledText(main, height=10, width=60, wrap=tk.WORD)
        self.input_text.pack(pady=5, padx=10, fill='x', expand=True)
        
        # Button Frame
        button_frame = ttk.Frame(main)
        button_frame.pack(pady=10)
        
        # Paste Button
        btn_paste = ttk.Button(
            button_frame, 
            text="Paste from Clipboard", 
            command=lambda: paste_paths(self.input_text, self.master)
        )
        btn_paste.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        btn_clear = ttk.Button(
            button_frame, 
            text="Clear Input", 
            command=lambda: clear_input(self.input_text)
        )
        btn_clear.pack(side=tk.LEFT, padx=5)
        
        # Process Button (Main Action)
        btn_process = ttk.Button(
            button_frame, 
            text="Process Paths", 
            command=self.run_path_processing,
            style='Accent.TButton' # Use an accented style if available for emphasis
        )
        btn_process.pack(side=tk.LEFT, padx=15)

        # Helper Label
        ttk.Label(
            main, 
            text="Files (Images) converted to WebP in a subfolder. Folders/CBZ archives are converted and re-zipped to a new .cbz.",
            font=('Arial', 8)
        ).pack(pady=5)
        
        # Keyboard shortcut for paste (Ctrl+V)
        def handle_ctrl_v(event):
            paste_paths(self.input_text, self.master)
            return "break" # Tells Tkinter to stop processing the event (i.e., suppress default paste)

        self.master.bind('<Control-v>', handle_ctrl_v)
        self.master.bind('<Control-V>', handle_ctrl_v)

        # === Status (Unchanged) ===
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main, textvariable=self.status_var, relief='sunken', anchor='w')
        status_bar.pack(fill='x', side='bottom', pady=(10,0))
        
    # --- UI and Validation Methods (Unchanged) ---
    def load_config_into_ui(self):
        self.quality_var.set(str(self.config.quality))
        self.lossless_var.set(self.config.lossless)
        self.cbz_var.set(self.config.save_as_cbz)
        self.method_var.set(str(self.config.webp_method))
        self.resize_var.set(self.config.resize_enabled)
        self.max_size_var.set(str(self.config.max_size))

    def save_config_from_ui(self):
        self.config.quality = int(self.quality_var.get() or 90)
        self.config.lossless = self.lossless_var.get()
        self.config.save_as_cbz = self.cbz_var.get()
        self.config.webp_method = int(self.method_var.get() or 4)
        self.config.resize_enabled = self.resize_var.get()
        self.config.max_size = int(self.max_size_var.get() or 1920)
        self.config.save()

    def validate_quality(self):
        try:
            q = int(self.quality_var.get())
            if not 0 <= q <= 100:
                raise ValueError
            return True
        except ValueError:
            messagebox.showerror("Invalid Quality", "Please enter a number between 0 and 100.", parent=self.master)
            self.quality_var.set("90")
            return False

    def validate_method(self):
        try:
            m = int(self.method_var.get())
            if not 1 <= m <= 6:
                raise ValueError
            return True
        except ValueError:
            messagebox.showerror("Invalid Effort", "Please enter a number between 1 and 6.", parent=self.master)
            self.method_var.set("4")
            return False
            
    def validate_max_size(self):
        try:
            s = int(self.max_size_var.get())
            if not s >= 1:
                raise ValueError
            return True
        except ValueError:
            messagebox.showerror("Invalid Size", "Please enter a valid pixel size (integer >= 1).", parent=self.master)
            self.max_size_var.set("1920")
            return False
            
    # --- New Core Processing Method ---

    def run_path_processing(self):
        """Takes input paths, separates them, calculates counts, and starts conversion."""
        if not (self.validate_quality() and self.validate_method() and self.validate_max_size()):
            return
        
        self.save_config_from_ui()

        input_paths = get_paths_from_input(self.input_text, self.master)
        
        if not input_paths:
            messagebox.showinfo("Processing", "No valid files, folders, or CBZ archives were entered for processing.")
            return

        files, folders, cbz = [], [], []
        
        for p in input_paths:
            p_lower = p.lower()
            if os.path.isfile(p):
                if p_lower.endswith('.cbz'):
                    cbz.append(p)
                elif p_lower.endswith(IMAGE_EXTS):
                    files.append(p)
                # Other file types are simply ignored
            elif os.path.isdir(p):
                folders.append(p)
        
        tasks = []
        if files:
            tasks.append({'kind': 'files', 'paths': files, 'count': len(files)})
        if folders:
            # Need to accurately count images in folders
            counts = sum(count_images_in_path(f) for f in folders)
            if counts > 0:
                tasks.append({'kind': 'folders', 'paths': folders, 'count': counts})
            else:
                # Optionally warn user if folders were entered but contained no images
                if len(folders) == 1:
                    messagebox.showwarning("Skipped Folder", f"Skipped folder '{os.path.basename(folders[0])}' because it contains no supported images.")
                elif len(folders) > 1:
                    messagebox.showwarning("Skipped Folders", f"Skipped {len(folders)} folders because they contain no supported images.")


        if cbz:
            # Use quick_scan for CBZ count estimate
            estimated_counts = sum(quick_scan_cbz_image_count(p) for p in cbz)
            tasks.append({'kind': 'cbz', 'paths': cbz, 'count': estimated_counts})
            
        if not tasks:
            messagebox.showinfo("Processing", "No supported images, folders, or CBZ archives found in the valid paths.")
            return

        self.start_conversion(tasks)

    # --- Worker Communication Methods (Unchanged) ---
    def start_conversion(self, tasks):
        # Validation is done in run_path_processing, only final setup here.
        total = sum(t['count'] for t in tasks)
        self.progress_window = ProgressWindow(self.master, total, self.cancel_conversion)
        
        self.worker = ConversionWorker(tasks, self.config, self.update_queue) 
        self.worker.start()

    def check_queue(self):
        try:
            while True:
                data = self.update_queue.get_nowait()
                self.process_update(data)
                self.update_queue.task_done()
        except queue.Empty:
            pass

        self.master.after(100, self.check_queue) 

    def process_update(self, data):
        kind = data.get('kind')
        msg = data.get('msg')
        done = data.get('done')
        total = data.get('total')
        
        if kind == "update" and self.progress_window:
            self.progress_window.update_progress(msg, done, total)
        elif kind == "cancelled":
            if self.progress_window:
                self.progress_window.close()
            self.status_var.set("Conversion cancelled.")
        elif kind == "done":
            log_lines = msg
            if self.progress_window:
                self.progress_window.close()
            self.show_final_report(log_lines)
            self.status_var.set("Conversion complete.")

    def cancel_conversion(self):
        if self.worker and self.worker.is_alive():
            self.worker.cancelled.set()
            self.status_var.set("Cancelling...")

    def show_final_report(self, log_lines: List[str]):
        successes = sum(1 for line in log_lines if "Converted" in line or "created" in line or "saved" in line)
        failures = sum(1 for line in log_lines if "Error" in line or "error" in line)

        report = f"Conversion Complete\n\n" \
                 f"Successful operations: {successes}\n" \
                 f"Failed operations: {failures}\n\n"

        if failures:
            report += "Failures:\n"
            for line in log_lines:
                if "Error" in line or "error" in line:
                    report += f"• {line}\n"

        log_path = os.path.expanduser("~/webp_conversion_log.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
            report += f"\nFull log saved to:\n{log_path}"
        except Exception as e:
            report += f"\nCould not save log file: {e}"

        messagebox.showinfo("Complete", report, parent=self.master)

class ProgressWindow:
# ... (ProgressWindow class is unchanged from the original v2 file)
# To save space, the full body of ProgressWindow is omitted here, but it remains identical.
# ----------------------------------------------------------------------
# (Skipping the unchanged ProgressWindow class body for brevity)
# ----------------------------------------------------------------------
    def __init__(self, master, total, on_cancel):
        self.window = tk.Toplevel(master)
        self.window.title("Converting...")
        self.window.geometry("520x140")
        self.window.transient(master)
        self.window.grab_set()

        ttk.Label(self.window, text="Starting conversion...", font=("", 10)).pack(pady=10)
        self.msg_label = ttk.Label(self.window, text="", foreground="blue")
        self.msg_label.pack(pady=5)

        self.bar = ttk.Progressbar(self.window, length=480, mode='determinate')
        self.bar.pack(pady=10)
        self.bar['maximum'] = total
        self.bar['value'] = 0
        self.total = total
        self.done = 0

        btns = ttk.Frame(self.window)
        btns.pack(pady=5)
        ttk.Button(btns, text="Cancel", command=on_cancel).pack(side='right', padx=10)
        
        self.window.protocol("WM_DELETE_WINDOW", on_cancel)

    def update_progress(self, msg, done, total):
        self.msg_label.config(text=msg)
        if total is not None and self.bar['maximum'] != total:
             self.bar['maximum'] = total
        
        if done is not None:
            self.bar['value'] = done
            self.done = done
            
        self.window.update_idletasks()

    def close(self):
        self.bar['value'] = self.bar['maximum'] 
        self.window.destroy()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if __name__ == '__main__':
    # Use standard tk.Tk instead of TkinterDnD.Tk
    root = tk.Tk() 
    app = WebPConverterApp(root)
    root.mainloop()