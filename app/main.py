import sys
import os
import subprocess
import shlex

BUILTINS = ["echo", "exit", "type", "pwd", "cd"]

def main():
    while True:
        sys.stdout.write("$ ")
    
        command = input().strip()
        if not command:
            continue #ignore empty input

        parts = shlex.split(command)
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
        elif cmd_name == 'pwd':
            print(os.getcwd())
        elif cmd_name == 'cd':
            if len(args) != 1:
                print("Usage: cd <absolute_path>")
                continue

            target_dir = args[0]
            if target_dir == "~":
                new_dir = os.environ.get("HOME", os.path.expanduser("~"))
            elif target_dir.startswith("/"):
                new_dir = target_dir # absolute path
            else:
                new_dir = os.path.join(os.getcwd(), target_dir) # relative path

            new_dir = os.path.normpath(new_dir)

            if os.path.isdir(new_dir):
                try:
                    os.chdir(new_dir)
                except Exception as e:
                    print(f"cd: {target_dir}: {e}")
            else: 
                print(f"cd: {target_dir}: No such file or directory")
        else:
            found = False
            for dir_path in os.environ.get("PATH", "").split(os.pathsep):
                full_path = os.path.join(dir_path, cmd_name)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK): #does file exist & is it executable
                    try:
                        subprocess.run([cmd_name] + args, executable=full_path)
                    except Exception as e:
                        print(f"Error executing {cmd_name}: {e}")
                    found = True
                    break
            if not found:
                print(f"{cmd_name}: command not found")


if __name__ == "__main__":
    main()
