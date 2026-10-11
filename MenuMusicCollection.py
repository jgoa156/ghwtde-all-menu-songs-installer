"""GHWT:DE Menu Music Collection: merges the menu music of the games you tick into ONE menu music mod.

GUI:  MenuMusicCollection.exe                      (a "sources" folder must sit next to the exe)
CLI:  MenuMusicCollection.exe --game <game folder> [--games GH5,WoR] [--disable-others]
      MenuMusicCollection.exe --out <folder> [--games GH5,WoR]     (build into a folder, for testing)
      other options: --sources <folder>, --log <file>, --list
      --games takes codes such as GH1, GH2, GH80s, GHA, GHM, GHSH, GHVH, GH5, BH, WoR, or all (the default).
Installer by WitchDoctoR; the menu music mods merged come from their own authors (see README.txt).
"""
import argparse
import os
import queue
import sys
import threading
import traceback

import mmc_core as core

TITLE = 'GHWT:DE Menu Music Collection'


def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- command line

def setup_console(log_path):
    """A windowed exe has no stdout: attach to the parent console when there is one, else discard output."""
    stream = None
    if os.name == 'nt' and sys.stdout is None:
        try:
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                stream = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        except Exception:
            stream = None
    if stream is None and sys.stdout is None:
        stream = open(os.devnull, 'w')
    if stream is not None:
        sys.stdout = sys.stderr = stream
    logf = open(log_path, 'w', encoding='utf-8') if log_path else None

    def say(text=''):
        print(text)
        sys.stdout.flush()
        if logf:
            logf.write(text + '\n')
            logf.flush()
    return say


def run_cli(argv):
    ap = argparse.ArgumentParser(prog='MenuMusicCollection', description=__doc__.split('\n')[0])
    ap.add_argument('--game', help='game folder (the one with GHWT_Definitive.exe): installs into DATA\\MODS')
    ap.add_argument('--games', default='all', help='comma separated: GH1,GH2,GH80s,GHA,GHM,GHSH,GHVH,GH5,BH,WoR or all')
    ap.add_argument('--out', help='build into this folder instead of the game (no GUI, no other-mod handling)')
    ap.add_argument('--sources', help='sources folder (default: "sources" next to the program)')
    ap.add_argument('--disable-others', action='store_true',
                    help='with --game: rename other menu music mods\' menumusic.ini to menumusic.ini.disabled')
    ap.add_argument('--list', action='store_true', help='list the games found in the sources folder and exit')
    ap.add_argument('--detect', action='store_true', help='print the game folder found automatically and exit')
    ap.add_argument('--log', help='also write the output to this file')
    log = None
    for i, a in enumerate(argv):
        if a == '--log' and i + 1 < len(argv):
            log = argv[i + 1]
        elif a.startswith('--log='):
            log = a.split('=', 1)[1]
    say = setup_console(log)
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if args.detect:
        say(core.detect_game_dir(app_dir()) or '(no game folder found)')
        return 0
    try:
        sources, problems = core.find_sources(args.sources or os.path.join(app_dir(), 'sources'))
        for folder, err in problems:
            say(f'WARNING: skipped a broken source: {err}')
        if not sources:
            raise core.MenuMusicError('No menu music sources found (a "sources" folder next to the program).')
        if args.list:
            for s in sources:
                say(f'{s.code:6s} {s.name:36s} {s.ntracks:3d} tracks {core.megabytes(s.nbytes):7.1f} MB  by {s.author}')
            return 0
        picked = core.select_games(sources, args.games)
        total = sum(s.nbytes for s in picked)
        say(f'Games: {", ".join(s.code for s in picked)}  ({sum(s.ntracks for s in picked)} tracks, '
            f'{core.megabytes(total):.1f} MB)')
        if core.megabytes(total) > core.BIG_BANK_MB:
            say(f'WARNING: over {core.BIG_BANK_MB} MB; the 32-bit game may hold the whole bank in memory.')
        if args.out:
            parent = args.out
        elif args.game:
            parent = core.check_game_dir(args.game)
        else:
            raise core.MenuMusicError('Give --game <game folder> or --out <folder>.')
        last = [-1]

        def progress(f, text):
            if int(f * 10) != last[0]:
                last[0] = int(f * 10)
                say(f'  {int(f * 100):3d}%  {text}')
        res = core.build_mod(parent, picked, progress)
        say(f'Built {res["mod"]}: {res["tracks"]} tracks, {core.megabytes(res["bytes"]):.1f} MB')
        for code, old, new in res['renames']:
            say(f'  renamed duplicate track {old} -> {new} ({code})')
        if args.game and not args.out:
            others = core.find_other_menu_mods(parent)
            for p in others:
                if args.disable_others:
                    say(f'  disabled: {core.disable_menu_mod(p)}')
                else:
                    say(f'  NOTE: another menu music mod is active (only one loads): {p}')
        return 0
    except core.MenuMusicError as e:
        say(f'ERROR: {e}')
        return 1
    except Exception:
        say('ERROR: ' + traceback.format_exc())
        return 2


# ---------------------------------------------------------------- GUI

def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(TITLE)
    root.minsize(620, 560)
    # explicit light colours: looks the same whatever Windows' own theme does to Tk
    bg, fg = '#f3f3f3', '#111111'
    root.configure(bg=bg)
    style = ttk.Style(root)
    if 'clam' in style.theme_names():
        style.theme_use('clam')
    style.configure('.', background=bg, foreground=fg, fieldbackground='#ffffff')
    style.configure('TButton', padding=(10, 3), background='#e1e1e1', foreground=fg)
    style.map('TButton', background=[('active', '#d0d0d0'), ('disabled', '#ececec')],
              foreground=[('disabled', '#888888')])
    style.configure('TCheckbutton', background=bg, foreground=fg)
    style.map('TCheckbutton', background=[('active', bg)])
    style.configure('TLabelframe', background=bg)
    style.configure('TLabelframe.Label', background=bg, foreground=fg)
    jobs = queue.Queue()
    state = {'busy': False}

    def crash(exc, val, tb):
        messagebox.showerror(TITLE, 'Something went wrong:\n\n' + ''.join(traceback.format_exception_only(exc, val)))
    root.report_callback_exception = crash

    sources_dir = os.path.join(app_dir(), 'sources')
    sources, problems = core.find_sources(sources_dir)
    if not sources:
        messagebox.showinfo(TITLE, 'No "sources" folder with menu music was found next to the program.\n\n'
                                   'Choose the sources folder.')
        picked_dir = filedialog.askdirectory(title='Choose the sources folder', parent=root)
        if picked_dir:
            sources_dir = picked_dir
            sources, problems = core.find_sources(sources_dir)
    if not sources:
        messagebox.showerror(TITLE, 'No menu music sources found. Keep the "sources" folder next to '
                                    'MenuMusicCollection.exe.')
        root.destroy()
        return 1
    if problems:
        messagebox.showwarning(TITLE, 'Some sources are broken and were skipped:\n\n' + '\n'.join(e for _, e in problems))

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill='both', expand=True)
    ttk.Label(frm, text='Main menu music from several games in ONE mod', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
    ttk.Label(frm, wraplength=580, justify='left',
              text='The game loads only one menu music mod, so the songs of the games you tick are merged into '
                   'one mod ("Main Menu Music Collection") that shuffles them all.').pack(anchor='w', pady=(2, 10))

    # game folder
    gbox = ttk.LabelFrame(frm, text='Game folder (the one with GHWT_Definitive.exe)', padding=8)
    gbox.pack(fill='x')
    game_var = tk.StringVar(value=core.detect_game_dir(app_dir()))
    ttk.Entry(gbox, textvariable=game_var).pack(side='left', fill='x', expand=True)

    def browse():
        d = filedialog.askdirectory(title='Choose the game folder', initialdir=game_var.get() or None, parent=root)
        if d:
            game_var.set(os.path.normpath(d))
    ttk.Button(gbox, text='Browse...', command=browse).pack(side='left', padx=(8, 0))

    # games
    lbox = ttk.LabelFrame(frm, text='Games', padding=8)
    lbox.pack(fill='x', pady=10)
    lbox.columnconfigure(0, weight=1)
    checks = []
    for r, s in enumerate(sources):
        v = tk.BooleanVar(value=True)
        checks.append((v, s))
        ttk.Checkbutton(lbox, text=s.name, variable=v, command=lambda: update_total()).grid(row=r, column=0, sticky='w')
        ttk.Label(lbox, text=f'{s.ntracks} tracks').grid(row=r, column=1, sticky='e', padx=(10, 0))
        ttk.Label(lbox, text=f'{core.megabytes(s.nbytes):.1f} MB', width=9, anchor='e').grid(row=r, column=2, sticky='e')
    bar = ttk.Frame(lbox)
    bar.grid(row=len(sources), column=0, columnspan=3, sticky='w', pady=(8, 0))

    def set_all(val):
        for v, _ in checks:
            v.set(val)
        update_total()
    ttk.Button(bar, text='Select all', command=lambda: set_all(True)).pack(side='left')
    ttk.Button(bar, text='Select none', command=lambda: set_all(False)).pack(side='left', padx=6)

    total_var = tk.StringVar()
    ttk.Label(frm, textvariable=total_var, font=('Segoe UI', 10, 'bold')).pack(anchor='w')
    warn_var = tk.StringVar()
    ttk.Label(frm, textvariable=warn_var, foreground='#b00020', wraplength=580, justify='left').pack(anchor='w')

    def chosen():
        return [s for v, s in checks if v.get()]

    def update_total():
        ch = chosen()
        size = sum(s.nbytes for s in ch)
        total_var.set(f'Total: {len(ch)} game{"" if len(ch) == 1 else "s"}, {sum(s.ntracks for s in ch)} tracks, '
                      f'{core.megabytes(size):.1f} MB')
        warn_var.set(f'Over {core.BIG_BANK_MB} MB: the game is 32-bit and may hold the whole bank in memory. '
                     'If it crashes or loads slowly, untick a few games.' if core.megabytes(size) > core.BIG_BANK_MB else '')
    update_total()

    prog = ttk.Progressbar(frm, maximum=100)
    prog.pack(fill='x', pady=(10, 2))
    status = tk.StringVar(value='Ready.')
    ttk.Label(frm, textvariable=status).pack(anchor='w')
    btns = ttk.Frame(frm)
    btns.pack(fill='x', pady=(10, 0))
    build_btn = ttk.Button(btns, text='Build')
    build_btn.pack(side='right')
    ttk.Button(btns, text='Close', command=root.destroy).pack(side='right', padx=8)

    def worker(game, ch):
        try:
            mods = core.check_game_dir(game)
            res = core.build_mod(mods, ch, lambda f, t: jobs.put(('progress', f, t)))
            jobs.put(('done', res, mods))
        except core.MenuMusicError as e:
            jobs.put(('error', str(e)))
        except Exception:
            jobs.put(('error', traceback.format_exc()))

    def finish_build(res, mods):
        msg = f'Done: {res["mod"]}\n{res["tracks"]} tracks, {core.megabytes(res["bytes"]):.1f} MB.'
        if res['renames']:
            msg += '\n\nDuplicate track names renamed: ' + ', '.join(f'{o} to {n}' for _, o, n in res['renames'])
        others = core.find_other_menu_mods(mods)
        if others:
            names = '\n'.join('  ' + os.path.basename(p) for p in others)
            if messagebox.askyesno(
                    TITLE, msg + '\n\nThe game loads only ONE menu music mod, and these other menu music mods are '
                    f'also in DATA\\MODS:\n\n{names}\n\nDisable them? Their menumusic.ini is renamed to '
                    'menumusic.ini.disabled (nothing is deleted; rename it back to re-enable).', parent=root):
                failed = []
                for p in others:
                    try:
                        core.disable_menu_mod(p)
                    except OSError as e:
                        failed.append(f'{os.path.basename(p)}: {e}')
                if failed:
                    messagebox.showerror(TITLE, 'Could not disable:\n' + '\n'.join(failed), parent=root)
                else:
                    messagebox.showinfo(TITLE, 'The other menu music mods are disabled. Start the game and enjoy.',
                                        parent=root)
            else:
                messagebox.showwarning(TITLE, 'Other menu music mods are still active. Only one loads: if the game '
                                       'plays the wrong music or freezes, disable the others.', parent=root)
        else:
            messagebox.showinfo(TITLE, msg + '\n\nStart the game and enjoy.', parent=root)

    def poll():
        try:
            while True:
                job = jobs.get_nowait()
                if job[0] == 'progress':
                    prog['value'] = job[1] * 100
                    status.set(job[2])
                else:
                    state['busy'] = False
                    build_btn.state(['!disabled'])
                    if job[0] == 'done':
                        status.set('Done.')
                        finish_build(job[1], job[2])
                    else:
                        prog['value'] = 0
                        status.set('Failed.')
                        messagebox.showerror(TITLE, job[1], parent=root)
        except queue.Empty:
            pass
        root.after(100, poll)

    def start_build():
        game = game_var.get().strip().strip('"')
        ch = chosen()
        if not ch:
            messagebox.showwarning(TITLE, 'Tick at least one game.', parent=root)
            return
        if not core.is_game_dir(game) and not messagebox.askyesno(
                TITLE, 'GHWT_Definitive.exe was not found in this folder. Install the mod here anyway?', parent=root):
            return
        if core.megabytes(sum(s.nbytes for s in ch)) > core.BIG_BANK_MB and not messagebox.askyesno(
                TITLE, f'The selection is over {core.BIG_BANK_MB} MB. The game is 32-bit and may hold the whole bank '
                       'in memory (crashes, slow start). Build anyway?', parent=root):
            return
        state['busy'] = True
        build_btn.state(['disabled'])
        prog['value'] = 0
        status.set('Starting...')
        threading.Thread(target=worker, args=(game, ch), daemon=True).start()

    build_btn.config(command=start_build)
    poll()
    root.mainloop()
    return 0


def main():
    if len(sys.argv) > 1:
        return run_cli(sys.argv[1:])
    return run_gui()


if __name__ == '__main__':
    sys.exit(main())
