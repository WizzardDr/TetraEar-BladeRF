"""
Build script to compile TETRA Decoder Modern GUI to standalone .exe
Uses PyInstaller to create a single-file executable with all dependencies.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_pyinstaller():
    """Check if PyInstaller is installed, install if not."""
    try:
        import PyInstaller
        print("[OK] PyInstaller is installed")
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("[OK] PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("[ERROR] Failed to install PyInstaller")
            return False

def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.absolute()

def build_exe():
    """Build the executable."""
    project_root = get_project_root()
    script_path = project_root / "tetra_gui_modern.py"
    
    if not script_path.exists():
        print(f"[ERROR] {script_path} not found!")
        return False
    
    print("=" * 60)
    print("TETRA Decoder Modern GUI - Build Script")
    print("=" * 60)
    print()
    
    # Check PyInstaller
    if not check_pyinstaller():
        return False
    
    # Prepare build directory
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"
    
    print(f"Project root: {project_root}")
    print(f"Script: {script_path}")
    print()
    
    # Collect data files to include
    data_files = []
    
    # Determine path separator for PyInstaller (semicolon on Windows, colon on Unix)
    path_sep = ";" if sys.platform == "win32" else ":"
    
    # Helper function to normalize path for PyInstaller
    # PyInstaller prefers forward slashes even on Windows
    def normalize_path(path):
        """Convert Path object to string with forward slashes for PyInstaller."""
        return str(path).replace("\\", "/")
    
    # DLLs - use absolute paths for better reliability
    dlls = ["librtlsdr.dll", "libusb-1.0.dll"]
    for dll in dlls:
        dll_path = project_root / dll
        if dll_path.exists():
            # PyInstaller format: source_path;destination_path
            # Use absolute path with forward slashes
            src_path = normalize_path(dll_path.absolute())
            data_files.append(f"--add-data={src_path}{path_sep}.")
            print(f"[OK] Including DLL: {dll}")
        else:
            print(f"[WARN] DLL not found: {dll}")
    
    # TETRA codec executables
    codec_dir = project_root / "tetra_codec" / "bin"
    if codec_dir.exists():
        codec_files = list(codec_dir.glob("*.exe"))
        for codec_file in codec_files:
            # Use absolute path for source, relative path for destination
            # PyInstaller format: source_path;destination_path
            src_path = normalize_path(codec_file.absolute())
            dst_path = "tetra_codec/bin"
            data_files.append(f"--add-data={src_path}{path_sep}{dst_path}")
            print(f"[OK] Including codec: {codec_file.name}")
    else:
        print("[WARN] Codec directory not found")
    
    # Python modules to include (hidden imports)
    hidden_imports = [
        "rtl_capture",
        "signal_processor",
        "tetra_decoder",
        "tetra_crypto",
        "tetra_protocol",
        "voice_processor",
        "frequency_scanner",
        "numpy",
        "scipy",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "sounddevice",
        "rtlsdr",
        "bitstring",
    ]
    
    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=TETRA_Decoder_Modern",
        "--onefile",  # Single executable file
        "--windowed",  # No console window (GUI app)
        "--clean",  # Clean cache
        "--noconfirm",  # Overwrite without asking
    ]
    
    # Add data files
    cmd.extend(data_files)
    
    # Add hidden imports
    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")
    
    # Add icon if available (optional)
    # Try .ico first, then .png from assets folder
    icon_path = None
    icon_ico = project_root / "assets" / "icon.ico"
    icon_png = project_root / "assets" / "icon_preview.png"
    
    if icon_ico.exists():
        icon_path = icon_ico
        cmd.append(f"--icon={icon_path}")
        print(f"[OK] Using icon: {icon_path}")
    elif icon_png.exists():
        # PyInstaller can use PNG files as icons
        icon_path = icon_png
        cmd.append(f"--icon={icon_path}")
        print(f"[OK] Using icon (PNG): {icon_path}")
    else:
        print("[INFO] No icon found in assets/ directory - building without icon")
    
    # Add the main script
    cmd.append(str(script_path))
    
    print()
    print("Building executable...")
    print("Command:", " ".join(cmd))
    print()
    
    try:
        # Run PyInstaller
        result = subprocess.run(cmd, cwd=project_root, check=True)
        
        # Check if exe was created
        exe_path = dist_dir / "TETRA_Decoder_Modern.exe"
        if exe_path.exists():
            print()
            print("=" * 60)
            print("[OK] Build successful!")
            print("=" * 60)
            print(f"Executable location: {exe_path}")
            print(f"Size: {exe_path.stat().st_size / (1024*1024):.2f} MB")
            print()
            print("Note: The executable includes all dependencies.")
            print("You can distribute this single .exe file.")
            print()
            
            # Copy DLLs to dist folder (PyInstaller might not bundle them correctly)
            print("Copying additional files to dist folder...")
            for dll in dlls:
                src = project_root / dll
                if src.exists():
                    dst = dist_dir / dll
                    shutil.copy2(src, dst)
                    print(f"  [OK] Copied {dll}")
            
            # Copy codec directory
            if codec_dir.exists():
                codec_dst = dist_dir / "tetra_codec" / "bin"
                codec_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(codec_dir, codec_dst, dirs_exist_ok=True)
                print(f"  [OK] Copied codec directory")
            
            return True
        else:
            print("[ERROR] Executable not found after build")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed with error code {e.returncode}")
        return False
    except Exception as e:
        print(f"[ERROR] Build error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    success = build_exe()
    if not success:
        sys.exit(1)
    
    print("Press Enter to exit...")
    try:
        input()
    except:
        pass

if __name__ == "__main__":
    main()
