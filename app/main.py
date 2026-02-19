import sys
import os
import subprocess
import shlex

BUILTINS = ["echo", "exit", "type", "pwd", "cd"]

def write_output(text, stdout_file):
    if stdout_file:
        with open(stdout_file, "a") as f:
            print(text, file=f)
    else:
        print(text)


def write_error(text, stderr_file):
    if stderr_file:
        with open(stderr_file, "a") as f:
            print(text, file=f)
    else:
        print(text, file=sys.stderr)


def main():
    while True:
        sys.stdout.write("$ ")
    
        command = input().strip()
        if not command:
            continue #ignore empty input

        parts = shlex.split(command)
        stdout_file = None
        stdout_append = False
        stderr_file = None
        stderr_append = False

        i = 0
        while i < len(parts):
            if parts[i] in (">", "1>"):
                if i + 1 >= len(parts):
                    print("syntax error: no file specified")
                    parts = []
                    break
                stdout_file = parts[i + 1]
                stdout_append = False
                del parts[i:i+2]
            elif parts[i] in (">>", "1>>"):
                if i + 1 >= len(parts):
                    print("syntax error: no file specified")
                    parts = []
                    break
                stdout_file = parts[i + 1]
                stdout_append = True
                del parts[i:i+2]
            elif parts[i] == "2>":
                if i + 1 >= len(parts):
                    print("syntax error: no file specified")
                    parts = []
                    break
                stderr_file = parts[i + 1]
                stderr_append = False
                del parts[i:i+2]
            elif parts[i] == "2>>":
                if i + 1 >= len(parts):
                    print("syntax error: no file specified")
                    parts = []
                    break
                stderr_file = parts[i + 1]
                stderr_append = True
                del parts[i:i+2]
            else:
                i += 1

        if not parts:
            continue

        # Create redirect target files immediately (like bash does).
        # Use "w" (truncate) for > and "a" (preserve) for >>.
        if stdout_file:
            open(stdout_file, "a" if stdout_append else "w").close()
        if stderr_file:
            open(stderr_file, "a" if stderr_append else "w").close()
        
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
                write_output(f"{target} is a shell builtin", stdout_file)
                continue

            found = False
            for dir_path in os.environ.get("PATH", "").split(os.pathsep):
                full_path = os.path.join(dir_path, target)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK): #does file exist & is it executable
                    write_output(f"{target} is {full_path}", stdout_file)
                    found = True
                    break
            if not found:
                write_error(f"{target}: not found", stderr_file)
        elif cmd_name == "echo":
            output = " ".join(args)
            write_output(output, stdout_file)
        elif cmd_name == 'pwd':
            output = os.getcwd()
            write_output(output, stdout_file)
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
                    write_error(f"cd: {target_dir}: {e}", stderr_file)
            else:
                write_error(f"cd: {target_dir}: No such file or directory", stderr_file)
        else:
            found = False
            for dir_path in os.environ.get("PATH", "").split(os.pathsep):
                full_path = os.path.join(dir_path, cmd_name)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK): #does file exist & is it executable
                    try:
                        stdout_arg = open(stdout_file, "a") if stdout_file else None
                        stderr_arg = open(stderr_file, "a") if stderr_file else None
                        try:
                            subprocess.run(
                                [cmd_name] + args,
                                executable=full_path,
                                stdout=stdout_arg,
                                stderr=stderr_arg,
                            )
                        finally:
                            if stdout_arg:
                                stdout_arg.close()
                            if stderr_arg:
                                stderr_arg.close()

                    except Exception as e:
                        print(f"Error executing {cmd_name}: {e}")
                    found = True
                    break
            if not found:
                write_error(f"{cmd_name}: command not found", stderr_file)


if __name__ == "__main__":
    main()
