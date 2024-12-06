from nanoid import generate

def generate_id(length: int = 10) -> str:
    """Generate a unique ID"""
    return generate("0123456789abcdefghijklmnopqrstuvwxyz", size=length)