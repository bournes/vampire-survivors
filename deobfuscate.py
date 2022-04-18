
import os
import re
import shutil
import jsbeautifier
from collections import deque
from progress.spinner import Spinner

sname = 'main.bundle.js'
mname = 'main.bundle.mod.js'
shift = 330
goffset = 215


def beautify_js(filename):
    opts = jsbeautifier.default_options()
    opts.indent_with_tabs = True

    print('-- Beautifing the script')
    with open(filename, 'r+', encoding='utf-8') as f:
        res = jsbeautifier.beautify(f.read(), opts)
        f.seek(0)
        f.write(res)
        f.truncate()


class NameNode:
    def __init__(self, name, is_parent=False):
        self.name = name
        self.is_parent = is_parent


class ReplacementNode(NameNode):
    def __init__(self, name, offset):
        super().__init__(name)
        self.offset = offset


class NamesTreeLevel:
    def __init__(self, depth):
        self.depth = depth
        self.nodes = []
        self.len = 0

    def insert(self, node):
        self.nodes.append(node)
        self.len += 1


class NamesTree:
    def __init__(self, root=None):
        self.levels = []
        self.max_level = -1

        self.add_level()
        if root is not None:
            self.level(0).insert(root)

    def level(self, depth):
        return self.levels[depth]

    def add_level(self):
        self.levels.append(NamesTreeLevel(self.max_level))
        self.max_level += 1

    def __str__(self) -> str:
        output = 'Tree Structure:\n'
        for depth, level in enumerate(self.levels):
            output += f"-- Level {depth}: {level.len} node{'s' if level.len > 1 else ''}\n"
        return output


def main():
    # cheking for backup
    if not os.path.isfile(f"{sname}.bak"):
        snamebak = f"{sname}.bak"

        print('Creating backup file:', snamebak)
        shutil.copyfile(sname, os.path.join(os.path.curdir, snamebak))

    # checking if file needs formatting
    with open(sname, 'r', encoding='utf-8') as f:
        if len(f.readlines()[0]) > 120:
            beautify_js(sname)

    gdict = []
    sdata = ''
    slines = []
    names_tree = None
    root_f = None

    print('Starting deobfuscation')

    with open(sname, 'r', encoding='utf-8') as f:
        sdata = f.read()
        f.seek(0)
        slines = f.readlines()

    def rotate(l, n):
        return l[-n:] + l[:-n]

    # get global dict
    print('-- Collecting global dict')
    dict_line = max(slines, key=len)
    dict_array_matches = re.search(r"\[.+\]", dict_line)
    if dict_array_matches is not None:
        gdict = dict_array_matches.group(0)[1:-1].split(', ')
        gdict = rotate(gdict, -shift)
    else:
        print('[ERRROR] Couldn\'t find global dict')
        exit(1)

    # collect all links to global dict
    spinner = Spinner('-- Collecting links to dict ')
    rootf_m = re.search(r"(?<=function ).+(?=\()", slines[0])
    if rootf_m is not None:
        root_f = NameNode(rootf_m.group(0), is_parent=True)
        names_tree = NamesTree(root_f)
    else:
        print('[ERROR] Couldn\'t find root dict function name')
        exit(1)

    prev_max = 0
    replacement_tree = NamesTree()
    while names_tree.level(names_tree.max_level).len > 0:
        # getting next level links...
        for node in names_tree.level(names_tree.max_level).nodes:
            fname_m = re.findall(re.compile(
                f"_0x\S*(?=\ = {node.name})"), sdata)
            for match in fname_m:

                if match == '_0x53ff38(0x562)':
                    print(match)

                if names_tree.max_level == prev_max:
                    names_tree.add_level()
                new_node = NameNode(match)
                names_tree.level(names_tree.max_level).insert(new_node)

            if not node.is_parent:
                # \%_fname%\(0x[a-z|0-9]+\) gets the %_fname%(%offset%)
                node_name_m = re.findall(re.compile(
                    f"\{node.name}\(0x[a-z|0-9]+\)"), sdata)
                for match in node_name_m:
                    # (?<=\%_fname%\()0x[a-z|0-9]+ extracts the %offset% from %_fname%(%offset%)
                    node_offset = re.search(re.compile(
                        f"(?<=\{node.name}\()0x[a-z|0-9]+"), match).group(0)
                    replacement_tree.level(0).insert(
                        ReplacementNode(f"{node.name}({node_offset})", node_offset))

            spinner.next()

        if (names_tree.max_level == prev_max):  # == prev_max
            break
        prev_max += 1
        spinner.next()

    spinner.finish()

    print('len repl:', len(replacement_tree.level(0).nodes))

    print('-- Replacing links with values from global dict')
    for count, rnode in enumerate(replacement_tree.level(0).nodes):

        # FIXME: skip first 9 nodes to start the game
        if count < 9:
            continue

        # replace [%_fname%(%offset%)] with .%gdict_val%
        sdata = sdata.replace(
            rnode.name, gdict[int(rnode.offset, 16) - goffset])

    with open(mname, 'w', encoding='utf-8') as f:
        f.write(sdata)

if __name__ == "__main__":
    main()
