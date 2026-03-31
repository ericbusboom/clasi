"""Number guessing game module for the Guessing Games package."""

SECRET_NUMBER = 7
MAX_GUESSES = 3


def play_number_game() -> None:
    """Run the 'Guess My Favorite Number' game loop."""
    print("=== Guess My Favorite Number ===")
    print(f"You have {MAX_GUESSES} guesses.")

    guess_num = 1
    while guess_num <= MAX_GUESSES:
        raw = input(f"Guess {guess_num}: ").strip()
        try:
            guess = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue

        if guess == SECRET_NUMBER:
            print("Correct! You got it!")
            return

        print("Nope, try again.")
        guess_num += 1

    print(f"Sorry! The answer was {SECRET_NUMBER}.")
