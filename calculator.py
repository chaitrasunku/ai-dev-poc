import sys

def get_numeric_input(prompt_message: str) -> float:
    """
    Prompts the user for numeric input, validates it, and re-prompts
    until a valid number (integer or float) is entered.
    
    Args:
        prompt_message (str): The message to display to the user when
                              prompting for input.

    Returns:
        float: The validated numeric input, converted to a float.
    """
    while True:
        user_input = input(prompt_message)
        try:
            # Attempt to convert the input to a float
            numeric_value = float(user_input)
            return numeric_value
        except ValueError:
            # If conversion fails, print an error and re-prompt
            print('Error: Please enter valid numbers.', file=sys.stdout)

if __name__ == '__main__':
    """
    Main execution block of the calculator program.
    Prompts for two numbers, calculates their sum, and displays the result.
    """
    print("Simple Addition Calculator")

    # Get the first number from the user
    num1 = get_numeric_input('Enter first number: ')

    # Get the second number from the user
    num2 = get_numeric_input('Enter second number: ')

    # Calculate the sum
    total_sum = num1 + num2

    # Display the result
    print(f'The sum is: {total_sum}')