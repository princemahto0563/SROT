import os

# Ensure standard system tool directories (Homebrew on Apple Silicon/Intel, standard Linux paths)
# are present in PATH so subprocess and shutil.which discover ffmpeg, ffprobe, tesseract, etc.
for p in ("/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "/usr/bin", "/bin"):
    if os.path.isdir(p) and p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = f"{p}{os.pathsep}" + os.environ.get("PATH", "")
