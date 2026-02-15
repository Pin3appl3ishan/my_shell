import sys


def main():
    while True:
        sys.stdout.write("$ ")
    
        command = input().strip()
        if not command:
            continue #ignore empty input

        parts = command.split()
        cmd_name = parts[0]
        args = parts[1:]

        if (cmd_name == "exit"):
            break
        elif cmd_name == "echo":
            print(" ".join(args))
        else:
            print(f"{cmd_name}: command not found")


if __name__ == "__main__":
    main()
