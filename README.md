# 🖼️ Advanced WebP + CBZ Converter (Simplified GUI)

A Python script with a graphical user interface (GUI) to batch convert images, folders, and existing CBZ archives into the efficient **WebP** format.

---

## ✨ Features

* **Single Input:** Paste file, folder, or CBZ paths into one box for batch processing.
* **WebP Control:** Configure Quality (0-100), Lossless mode, and Conversion Effort (1-6).
* **Optional Resizing:** Downscale images using the Lanczos algorithm to limit the longest side (e.g., max 1920px).
* **CBZ Handling:**
    * Converts image folders into new `.cbz` archives containing WebP images.
    * Converts the contents of existing `.cbz` archives and creates a new `_webp.cbz`.

---

## 🛠️ Requirements

* Python 3
* `Pillow` (PIL) library
* `tkinter` (Standard Python library)

## 🚀 How to Use

1.  **Run the script:**
    ```bash
    python webp cbz creator.py
    ```
2.  **Configure Settings:** Adjust the Quality, Lossless, Effort, and Resize options.
3.  **Paste Paths:** Paste one or more full paths (files, folders, or `.cbz` archives) into the input box, one per line.
4.  **Click "Process Paths"** to start the batch conversion. A separate progress window will appear.
