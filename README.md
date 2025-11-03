# webp cbz creator

A **simplified GUI tool** written in Python (Tkinter/Pillow) for **batch converting** images, folders, and existing `.cbz` archives into the highly efficient **WebP** format.

---

## 📸 Preview

A screenshot of the application's user interface:

![App Screenshot](https://github.com/Xzpy909/webp-cbz-creator/blob/main/preview.png)

---

## ✨ Key Features

* **Batch Conversion:** Converts multiple files, folders, or CBZ paths in one go.
* **Quality Control:** Adjust **Lossless** mode, **Quality** (0-100), and **Effort** level.
* **Resizing:** Optional **Lanczos downscaling** to cap the image's longest side (e.g., 1920px).
* **CBZ Handling:** Creates new CBZ archives from converted images or re-encodes existing ones.

---

## 🚀 Setup & Run

1.  **Install Pillow:**
    ```bash
    pip install Pillow
    ```

2.  **Run the script:**
    ```bash
    python "webp cbz creator.py"
    ```

Simply paste your file/folder paths into the box, configure your WebP settings, and click "Process Paths".
