=== FILE: calculator.py ===
def get_numeric_input(prompt_message: str) -> float:
    """
    Prompts the user for numeric input, validates it, and returns a float.
    Continuously re-prompts until valid numeric input is provided.
    """
    while True:
        user_input = input(prompt_message)
        try:
            # Attempt to convert the input to a floating-point number
            number = float(user_input)
            return number
        except ValueError:
            # If conversion fails, print an error and re-prompt
            print('Error: Please enter valid numbers.')

def calculate_sum(num1: float, num2: float) -> float:
    """
    Calculates the sum of two floating-point numbers.
    """
    return num1 + num2

if __name__ == '__main__':
    # Get the first number from the user
    first_number = get_numeric_input('Enter the first number: ')
    
    # Get the second number from the user
    second_number = get_numeric_input('Enter the second number: ')
    
    # Calculate the sum of the two numbers
    total_sum = calculate_sum(first_number, second_number)
    
    # Display the result to the user
    print(f'The sum is: {total_sum}')
=== END FILE ===
=== FILE: README.md ===
# Simple Addition Calculator

This lightweight command-line program takes two numbers as input and returns their sum.

## Usage

To run the calculator, execute the following command in your terminal:

```bash
python calculator.py
```

When prompted, the program will ask for two numbers. Please enter valid numeric values (integers or floating-point numbers).

- Example 1 (Integers): When prompted, enter '2' for the first number and '3' for the second. Expected output: The sum is: 5.0
- Example 2 (Floating-point): When prompted, enter '10.5' for the first number and '4.5' for the second. Expected output: The sum is: 15.0
- Example 3 (Invalid Input Handling): If invalid input (e.g., 'abc') is provided, the program will display an error message and re-prompt: 'Error: Please enter valid numbers.'
=== END FILE ===