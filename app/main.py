import sys
import os
import subprocess
import shlex
import readline

BUILTINS = ["echo", "exit", "type", "pwd", "cd"]


_matches_cache: list[str] = []


def _completer(text, state):
    global _matches_cache
    if state == 0:
        matches = [b + " " for b in BUILTINS if b.startswith(text)]
        for dir_path in os.environ.get("PATH", "").split(os.pathsep):
            try:
                for name in os.listdir(dir_path):
                    if name.startswith(text):
                        full = os.path.join(dir_path, name)
                        if os.path.isfile(full) and os.access(full, os.X_OK):
                            candidate = name + " "
                            if candidate not in matches:
                                matches.append(candidate)
            except OSError:
                continue
        matches.sort(key=lambda m: m.rstrip())
        _matches_cache = matches
    return _matches_cache[state] if state < len(_matches_cache) else None


def _display_matches(substitution, matches, longest_match_len):
    names = sorted(m.rstrip() for m in matches)
    sys.stdout.write("\n" + "  ".join(names) + "\n")
    sys.stdout.write("$ " + readline.get_line_buffer())
    sys.stdout.flush()


readline.set_completer(_completer)
readline.set_completion_display_matches_hook(_display_matches)
readline.parse_and_bind("tab: complete")


def write_output(text, out):
    print(text, file=out if out is not None else sys.stdout)


def write_error(text, err):
    print(text, file=err if err is not None else sys.stderr)


def _find_executable(name):
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        full = os.path.join(dir_path, name)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


def _run_pipeline(left_parts, right_parts):
    left_exe = _find_executable(left_parts[0])
    right_exe = _find_executable(right_parts[0])
    p1 = subprocess.Popen(
        left_parts,
        executable=left_exe,
        stdout=subprocess.PIPE,
    )
    p2 = subprocess.Popen(
        right_parts,
        executable=right_exe,
        stdin=p1.stdout,
    )
    p1.stdout.close()   # lets p2's exit send SIGPIPE to p1
    p2.wait()
    p1.wait()


def main():
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        command = input().strip()
        if not command:
            continue

        parts = shlex.split(command)

        if "|" in parts:
            pipe_idx = parts.index("|")
            left, right = parts[:pipe_idx], parts[pipe_idx + 1:]
            if left and right:
                _run_pipeline(left, right)
            continue

        stdout_file = None
        stdout_append = False
        stderr_file = None
        stderr_append = False

        i = 0
        while i < len(parts):
            if parts[i] in (">", "1>"):
                if i + 1 >= len(parts):
                    write_error("syntax error: no file specified", None)
                    parts = []
                    break
                stdout_file = parts[i + 1]
                stdout_append = False
                del parts[i:i+2]
            elif parts[i] in (">>", "1>>"):
                if i + 1 >= len(parts):
                    write_error("syntax error: no file specified", None)
                    parts = []
                    break
                stdout_file = parts[i + 1]
                stdout_append = True
                del parts[i:i+2]
            elif parts[i] == "2>":
                if i + 1 >= len(parts):
                    write_error("syntax error: no file specified", None)
                    parts = []
                    break
                stderr_file = parts[i + 1]
                stderr_append = False
                del parts[i:i+2]
            elif parts[i] == "2>>":
                if i + 1 >= len(parts):
                    write_error("syntax error: no file specified", None)
                    parts = []
                    break
                stderr_file = parts[i + 1]
                stderr_append = True
                del parts[i:i+2]
            else:
                i += 1

        if not parts:
            continue

        cmd_name = parts[0]
        args = parts[1:]

        if cmd_name == "exit":
            break

        # Open redirect files once with the correct mode before running the command.
        out = None
        err = None
        if stdout_file:
            try:
                out = open(stdout_file, "a" if stdout_append else "w")
            except OSError as e:
                write_error(f"{stdout_file}: {e.strerror}", None)
                continue
        if stderr_file:
            try:
                err = open(stderr_file, "a" if stderr_append else "w")
            except OSError as e:
                if out is not None:
                    out.close()
                write_error(f"{stderr_file}: {e.strerror}", None)
                continue

        try:
            if cmd_name == "type":
                if len(args) != 1:
                    write_error("type: expected one argument", err)
                elif args[0] in BUILTINS:
                    write_output(f"{args[0]} is a shell builtin", out)
                else:
                    target = args[0]
                    full_path = _find_executable(target)
                    if full_path:
                        write_output(f"{target} is {full_path}", out)
                    else:
                        write_error(f"{target}: not found", err)

            elif cmd_name == "echo":
                write_output(" ".join(args), out)

            elif cmd_name == "pwd":
                write_output(os.getcwd(), out)

            elif cmd_name == "cd":
                if len(args) != 1:
                    write_error("cd: expected one argument", err)
                else:
                    target_dir = args[0]
                    if target_dir == "~":
                        new_dir = os.environ.get("HOME", os.path.expanduser("~"))
                    elif os.path.isabs(target_dir):
                        new_dir = target_dir
                    else:
                        new_dir = os.path.join(os.getcwd(), target_dir)
                    new_dir = os.path.normpath(new_dir)
                    if os.path.isdir(new_dir):
                        try:
                            os.chdir(new_dir)
                        except Exception as e:
                            write_error(f"cd: {target_dir}: {e}", err)
                    else:
                        write_error(f"cd: {target_dir}: No such file or directory", err)

            else:
                full_path = _find_executable(cmd_name)
                if full_path:
                    try:
                        subprocess.run(
                            [cmd_name] + args,
                            executable=full_path,
                            stdout=out,
                            stderr=err,
                        )
                    except Exception as e:
                        write_error(f"Error executing {cmd_name}: {e}", None)
                else:
                    write_error(f"{cmd_name}: command not found", err)

        finally:
            if out is not None:
                out.close()
            if err is not None:
                err.close()


if __name__ == "__main__":
    main()
