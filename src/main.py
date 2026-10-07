import sys
import os

# Ensure the root directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui import AppUI

def main():
    app = AppUI()
    app.mainloop()

if __name__ == "__main__":
    main()
