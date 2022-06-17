import argparse
import readline
import sys
import re

op_names = ['lw', 'sw', 'add', 'addi', 'sub', 'and', 'andi', 'beqz', 'j', 'halt', 'noop']


class Instr:
    def __init__(self, t: str, opcode=0, rs1=0, rs2=0, rd=0, imm=0, func=0):
        if t == 'I':
            self.binary = '{0:06b}'.format(opcode%2**6) + '{0:05b}'.format(rs1%2**5) + '{0:05b}'.format(rd%2**5) + '{0:016b}'.format(imm%2**16)
        elif t == 'R':
            self.binary = '{0:06b}'.format(opcode%2**6) + '{0:05b}'.format(rs1%2**5) + '{0:05b}'.format(rs2%2**5) + '{0:05b}'.format(rd%2**5) + '{0:011b}'.format(func%2**11)
        elif t == 'J':
            self.binary = '{0:06b}'.format(opcode%2**6) + '{0:026b}'.format(imm%2**26)

    def to_bytes(self):
        return int(self.binary, 2).to_bytes(4, byteorder='big')

    def to_int(self):
        return (int(self.binary, 2) + 2**31) % 2**32 - 2**31


class Assembler:

    def __init__(self):
        self.incnt = 0
        self.outcnt = 0
        self.flags = {}
        self.wait = None
        self.queue = []

    def assemble_line(self, line: str):
        res = []

        if line.find(';') >= 0:
            line = line[:line.find(';')]
        line = line.lstrip().rstrip().lower()
        splits = re.split(r'[,\s]+', line)

        # see if there's new flag
        if splits[0] not in op_names and not splits[0].isdigit():   # line begin with flag
            self.flags[splits[0]] = self.incnt
            del splits[0]
        if len(splits) > 0:
            self.queue.append(splits)
            self.incnt += 1

        # try assemble from beginning of queue
        while len(self.queue) > 0:
            splits = self.queue[0]

            if splits[0] == 'j':
                if len(splits) != 2 or splits[1] not in self.flags.keys():
                    raise Exception(line)
                if splits[1] not in self.flags.keys():
                    break
                res.append(Instr(t='J', opcode=2, imm=self.flags[splits[1]]-self.outcnt-1))
            
            elif splits[0] == 'halt':
                if len(splits) != 1:
                    raise Exception(line)
                res.append(Instr(t='J', opcode=1, imm=0))
            
            elif splits[0] == 'noop':
                if len(splits) != 1:
                    raise Exception(line)
                res.append(Instr(t='J', opcode=3, imm=0))

            elif splits[0] == 'lw':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='I', opcode=35, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), imm=int(splits[3])))

            elif splits[0] == 'sw':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='I', opcode=43, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), imm=int(splits[3])))

            elif splits[0] == 'beqz':
                if len(splits) != 3:
                    raise Exception(line)
                if splits[2] not in self.flags.keys():
                    break
                res.append(Instr(t='I', opcode=4, rd=0, rs1=int(splits[1].lstrip('r')), imm=self.flags[splits[2]]-self.outcnt-1))
            
            elif splits[0] == 'addi':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='I', opcode=8, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), imm=int(splits[3])))

            elif splits[0] == 'andi':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='I', opcode=12, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), imm=int(splits[3])))

            elif splits[0] == 'add':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='R', opcode=0, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), rs2=int(splits[3].lstrip('r')), func=32))

            elif splits[0] == 'sub':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='R', opcode=0, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), rs2=int(splits[3].lstrip('r')), func=34))

            elif splits[0] == 'and':
                if len(splits) != 4:
                    raise Exception(line)
                res.append(Instr(t='R', opcode=0, rd=int(splits[1].lstrip('r')), rs1=int(splits[2].lstrip('r')), rs2=int(splits[3].lstrip('r')), func=36))

            else:
                raise Exception(line)
            
            self.outcnt += 1
            del self.queue[0]
        
        return res


def main():

    def arg_parse():
        parser = argparse.ArgumentParser(description="mips32 assembler")

        parser.add_argument("-i", "--input", default=None, type=str, help="input file path, None: stdin")
        parser.add_argument("-o", "--output", default=None, type=str, help="output file path, None: stdout")
        args = parser.parse_args()
        return args

    args = arg_parse()

    asm = Assembler()

    res = []
    if args.input is None:
        line = sys.stdin.readline()
        while line:
            instrs = asm.assemble_line(line)
            for instr in instrs:
                print(instr.to_int())
            res.extend(instrs)
            line = sys.stdin.readline()
    else:
        with open(args.input, "r") as f:
            line = f.readline()
            while line:
                instrs = asm.assemble_line(line)
                for instr in instrs:
                    print(instr.to_int())
                res.extend(instrs)
                line = f.readline()

    if args.output is not None:
        with open(args.output, "w") as f:
            for instr in res:
                f.write(str(instr.to_int()) + '\n')


if __name__ == "__main__":
    main()