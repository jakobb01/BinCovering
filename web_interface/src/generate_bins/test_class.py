import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from generate import Generate  # Assuming you saved the class above in mymodule.py

class JakobB(Generate):
    def start(self):
        return "My custom start"

    def next(self):
        return 42

    def stop(self):
        return "Done"

gen = JakobB()
print(gen.start())  # Output: My custom start
print(gen.next())   # Output: 42
print(gen.stop())   # Output: Done
