import sys
import os
import subprocess

BUILTINS = ["echo", "exit", "type"]

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
        elif cmd_name == "type":
            if len(args) != 1:
                print("Usage: type <command>")
                continue
            target = args[0]

            if target in BUILTINS:
                print(f"{target} is a shell builtin")
                continue

            found = False
            for dir_path in os.environ.get("PATH", "").split(os.pathsep):
                full_path = os.path.join(dir_path, target)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK): #does file exist & is it executable
                    print(f"{target} is {full_path}")
                    found = True
                    break
            if not found:
                print(f"{target}: not found")
        elif cmd_name == "echo":
            print(" ".join(args))
        else:
            found = False
            for dir_path in os.environ.get("PATH", "").split(os.pathsep):
                full_path = os.path.join(dir_path, cmd_name)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK): #does file exist & is it executable
                    try:
                        subprocess.run([full_path] + args)
                    except Exception as e:
                        print(f"Error executing {cmd_name}: {e}")
                    found = True
                    break
                if not found:
                    print(f"{cmd_name}: command not found")


if __name__ == "__main__":
    main()
