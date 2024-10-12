def compare_strings(str1, str2):
    # Find the index of the first difference
    idx = next((i for i in range(min(len(str1), len(str2))) if str1[i] != str2[i]), None)

    if idx is None:
        if len(str1) == len(str2):
            print("The strings are identical.")
            return
        idx = min(len(str1), len(str2))

    # Calculate the start and end indices for context
    start = max(0, idx - 20)
    end = min(max(len(str1), len(str2)), idx + 21)

    # Print the context
    print(f"First difference at index {idx}:")
    print(f"{str1[start:end]}")
    print(f"{str2[start:end]}")
    print(" " * (idx - start) + "^")
