# This function prompts the user for numeric input,
# validates it, and re-prompts until valid input is received.
def get_numeric_input(prompt_message):
    """
    Prompts the user for a number, validates the input, and returns it as a float.
    Continuously re-prompts with an error message until valid numeric input is provided.

    Args:
        prompt_message (str): The message to display to the user.

    Returns:
        float: The valid numeric input provided by the user.
    """
    while True:
        user_input = input(prompt_message)
        try:
            # Attempt to convert the input to a float
            numeric_value = float(user_input)
            return numeric_value
        except ValueError:
            # If conversion fails, print an error and re-prompt
            print("Error: Please enter valid numbers.")

# This function calculates the sum of two numbers.
def calculate_sum(num1, num2):
    """
    Calculates the sum of two numbers.

    Args:
        num1 (float): The first number.
        num2 (float): The second number.

    Returns:
        float: The sum of num1 and num2.
    """
    return num1 + num2

# Main program logic
if __name__ == '__main__':
    # Get the first number from the user
    first_number = get_numeric_input('Enter the first number: ')

    # Get the second number from the user
    second_number = get_numeric_input('Enter the second number: ')

    # Calculate the sum of the two numbers
    total_sum = calculate_sum(first_number, second_number)

    # Display the result
    print(total_sum)