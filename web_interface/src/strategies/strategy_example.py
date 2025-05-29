# strategy_example.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from strategy import Strategy


# define your methods for the strategy
class MyStrategy(Strategy):
    def start(self):
        return "Custom start"

    def next(self):
        return "Custom next step"

    def stop(self):
        return "Custom stop"

# Example usage
if __name__ == "__main__":
    strat = MyStrategy(filename="output.txt")  # File is opened during init
    print(strat.start())      # Custom start
    print(strat.next())       # Custom next step
    print(strat.stop())       # Custom stop

    if strat.file:
        strat.file.write("Logging from strategy...\n")
        strat.file.close()
