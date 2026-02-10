def get_validated_number(prompt_message):
    """
    Prompts the user for a number, validates it, and returns the parsed float
    or an error message.
    """
    user_input = input(prompt_message)
    try:
        number_value = float(user_input)
        return number_value, None
    except ValueError:
        return None, 'Error: Please enter valid numbers.'

def main():
    """
    Main function for the Simple Addition Calculator CLI.
    Prompts for two numbers, validates them, calculates their sum,
    and displays the result or an error.
    """
    num1_value, num1_error = get_validated_number('Enter the first number: ')

    if num1_error:
        print(num1_error)
        return

    num2_value, num2_error = get_validated_number('Enter the second number: ')

    if num2_error:
        print(num2_error)
        return

    # If both inputs are valid, calculate and print the sum
    sum_result = num1_value + num2_value
    print(sum_result)

if __name__ == '__main__':
    main()