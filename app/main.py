import sys
import os
import subprocess
import shlex
import readline
import threading

BUILTINS = ["echo", "exit", "type", "pwd", "cd", "history"]


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


def _run_builtin(parts, stdout=None):
    cmd_name = parts[0]
    args = parts[1:]
    out = stdout if stdout is not None else sys.stdout
    if cmd_name == "echo":
        print(" ".join(args), file=out)
    elif cmd_name == "type":
        if not args:
            print("type: expected one argument", file=sys.stderr)
        else:
            target = args[0]
            if target in BUILTINS:
                print(f"{target} is a shell builtin", file=out)
            else:
                full_path = _find_executable(target)
                if full_path:
                    print(f"{target} is {full_path}", file=out)
                else:
                    print(f"{target}: not found", file=sys.stderr)
    elif cmd_name == "pwd":
        print(os.getcwd(), file=out)


def _find_executable(name):
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        full = os.path.join(dir_path, name)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


def _run_pipeline(stages):
    n = len(stages)
    # Create n-1 pipes; pipes[i] connects stage i's stdout to stage i+1's stdin.
    pipes = [os.pipe() for _ in range(n - 1)]  # each entry: (r_fd, w_fd)

    procs = []          # list of (Popen | None, Thread | None)
    fds_to_close = []   # raw fds the parent must close after spawning all stages

    for i, stage in enumerate(stages):
        in_fd  = pipes[i - 1][0] if i > 0     else None  # read end of prev pipe
        out_fd = pipes[i][1]     if i < n - 1 else None  # write end of next pipe

        if stage[0] in BUILTINS:
            out_file = os.fdopen(out_fd, 'w') if out_fd is not None else None
            if in_fd is not None:
                os.close(in_fd)  # builtins ignore stdin; close read end now
            def make_target(s, o):
                def _target():
                    _run_builtin(s, stdout=o)
                    if o is not None:
                        o.close()
                return _target
            t = threading.Thread(target=make_target(stage, out_file))
            t.start()
            procs.append((None, t))
        else:
            kwargs = {}
            if in_fd is not None:
                kwargs['stdin'] = in_fd
                fds_to_close.append(in_fd)
            if out_fd is not None:
                kwargs['stdout'] = out_fd
                fds_to_close.append(out_fd)
            p = subprocess.Popen(stage, executable=_find_executable(stage[0]), **kwargs)
            procs.append((p, None))

    # Parent drops its copies of all fds handed to Popen.
    for fd in fds_to_close:
        try:
            os.close(fd)
        except OSError:
            pass

    # Wait last-to-first: each stage's exit closes its read end, sending
    # SIGPIPE to the stage before it, propagating the shutdown backward.
    for proc, thread in reversed(procs):
        if thread:
            thread.join()
        if proc:
            proc.wait()


def main():
    HISTORY: list[str] = []
    
    while True:
        line = input("$ ")
        if not line.strip():
            continue
        
        HISTORY.append(line)        

        parts = shlex.split(line)

        if "|" in parts:
            stages = []
            current = []
            for token in parts:
                if token == "|":
                    if current:
                        stages.append(current)
                    current = []
                else:
                    current.append(token)
            if current:
                stages.append(current)
            if len(stages) >= 2:
                _run_pipeline(stages)
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
            elif cmd_name == "history":
                if len(args) >= 2 and args[0] == "-r":
                    path = args[1]
                    try: 
                        with open(path, "r") as f:
                            for line in f:
                                HISTORY.append(line.rstrip("\n"))
                    except OSError as e:
                        write_error(f"history: {e.strerror}", err)
                    continue
                
                if len(args) == 0:
                    start_index = 0
                elif len(args) == 1 and args[0].isdigit():
                    n = int(args[0])
                    start_index = max(len(HISTORY) - n, 0)
                else:
                    write_error("history: invalid argument", err)
                    continue
                
                for idx in range(start_index, len(HISTORY)):
                    print(f"{idx:>5}  {HISTORY[idx]}")           
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
