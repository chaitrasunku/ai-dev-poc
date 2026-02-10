# calculator.py

def main():
    """
    Main function for the Simple Addition Calculator.
    Prompts user for two numbers, validates input, calculates their sum,
    and displays the result or an error message.
    """
    print("--- Simple Addition Calculator ---")

    # Prompt for the first number
    num1_str = input("Enter the first number: ")

    # Validate and convert the first input to a float
    try:
        num1 = float(num1_str)
    except ValueError:
        print("Error: Please enter valid numbers.")
        return  # Exit the program if the first input is invalid

    # Prompt for the second number
    num2_str = input("Enter the second number: ")

    # Validate and convert the second input to a float
    try:
        num2 = float(num2_str)
    except ValueError:
        print("Error: Please enter valid numbers.")
        return  # Exit the program if the second input is invalid

    # Calculate the sum
    sum_result = num1 + num2

    # Display the sum
    print(f"The sum is: {sum_result}")

if __name__ == "__main__":
    main()