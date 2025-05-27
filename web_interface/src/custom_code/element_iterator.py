# element_iterator.py

class ElementIterator:
    """Iterator to read integer elements from a file line by line."""

    def __init__(self, filename):
        try:
            self.file = open('./src/data/'+filename, 'r')
        except FileNotFoundError:
            raise RuntimeError(f"Failed to open file for reading: {filename}")

    def get_next_element(self):
        """Return the next integer from the file, or None if EOF is reached."""
        line = self.file.readline()
        if not line:
            return None
        return int(line.strip())

    def __del__(self):
        """Ensure file is closed when the object is destroyed."""
        if hasattr(self, 'file') and not self.file.closed:
            self.file.close()
