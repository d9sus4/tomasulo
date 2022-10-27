from email.policy import default
from platform import machine
import tkinter as tk
from tkinter import filedialog as fd
import ctypes
from ctypes import *
import time
from assembler import *

SIZE_ROB = 16

WINDOW_SIZE = '720x960'

WIDTH_CANVAS_ROB = 650
HEIGHT_CANVAS_ROB = 200

WIDTH_CANVAS_RES = 650
HEIGHT_CANVAS_RES = 150

WIDTH_CANVAS_REGFILE = 250
HEIGHT_CANVAS_REGFILE = 300

WIDTH_CANVAS_MEMORY = 150
HEIGHT_CANVAS_MEMORY = 300

YPAD_TITLES = 10

WIDTH_LABEL_SHORT = 5
WIDTH_LABEL_MID = 7
WIDTH_LABEL_LONG = 10

MS_PER_CYCLE = 100

PATH_SO = "./bin/libtomasulo.so"

UNITS = {
    1: "LOAD1",
    2: "LOAD2",
    3: "STORE1",
    4: "STORE2",
    5: "INT1",
    6: "INT2",
}

STATES = {
    0: "Issue",
    1: "Execute",
    2: "Write",
    3: "Commit",
}


class resStation(Structure):
    _fields_ = [
        ("instr", c_int),
        ("busy", c_int),
        ("Vj", c_int),
        ("Vk", c_int),
        ("Qj", c_int),
        ("Qk", c_int),
        ("exTimeLeft", c_int),
        ("reorderNum", c_int),
    ]

class reorderEntry(Structure):
    _fields_ = [
        ("busy", c_int),
        ("instr", c_int),
        ("execUnit", c_int),
        ("instrState", c_int),
        ("valid", c_int),
        ("result", c_int),
        ("storeAddress", c_int),
    ]

class regResultEntry(Structure):
    _fields_ = [
        ("valid", c_int),
        ("reorderNum", c_int),
    ]

class btbEntry(Structure):
    _fields_ = [
        ("valid",c_int),
        ("branchPC", c_int),
        ("branchTarget", c_int),
        ("branchPred", c_int),
    ]

class machineState(Structure):
    _fields_ = [
        ("pc", c_int),
        ("cycles", c_int),
        ("reservation", resStation*6),
        ("reorderBuf", reorderEntry*SIZE_ROB),
        ("headRB", c_int),
        ("tailRB", c_int),
        ("regResult", regResultEntry*32),
        ("btBuf", btbEntry*8),
        ("memory", c_int*10000),
        ("memorySize", c_int),
        ("regFile", c_int*32),
        ("halt", c_int),
    ]

class RegfileFrame(tk.Frame):
    def __init__(self, parent, num_regs=32):

        tk.Frame.__init__(self, parent)
        self.canvas = tk.Canvas(self, width=WIDTH_CANVAS_REGFILE, height=HEIGHT_CANVAS_REGFILE)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=tk.TRUE)
        self.scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.FALSE)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', self.on_configure)
        self.frame_inner = tk.Frame(self.canvas)
        self.frame_inner.bind('<Configure>', self.on_configure)
        self.canvas.create_window(0, 0, window=self.frame_inner, anchor=tk.NW)
        self.regs = []
        
        self.label_name = tk.Label(self.frame_inner, text='Name', width=WIDTH_LABEL_SHORT)
        self.label_name.grid(row=0, column=0)
        self.label_value = tk.Label(self.frame_inner, text='Value', width=WIDTH_LABEL_LONG)
        self.label_value.grid(row=0, column=1)
        self.label_valid = tk.Label(self.frame_inner, text='Valid', width=WIDTH_LABEL_SHORT)
        self.label_valid.grid(row=0, column=2)
        self.label_rob_idx = tk.Label(self.frame_inner, text='ROBidx', width=WIDTH_LABEL_SHORT)
        self.label_rob_idx.grid(row=0, column=3)
        for i in range(num_regs):
            label_name = tk.Label(self.frame_inner, text='r'+str(i), width=WIDTH_LABEL_SHORT)
            label_name.grid(row=i+1, column=0)
            label_value = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_value.grid(row=i+1, column=1)
            label_valid = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_valid.grid(row=i+1, column=2)
            label_rob_idx = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_rob_idx.grid(row=i+1, column=3)
            self.regs.append([label_name, label_value, label_valid, label_rob_idx])
        for i in range(4):
            self.grid_columnconfigure(i, weight=1)
    
    def refresh(self, regFile, regResult):
        for i, reg in enumerate(self.regs):
            reg[1].configure(text=str(regFile[i]))
            reg[2].configure(text=str(regResult[i].valid))
            if regResult[i].valid == 1:
                reg[3].configure(text='-')
            else:
                reg[3].configure(text=str(regResult[i].reorderNum))
            
    def on_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox(tk.ALL))

class MemoryFrame(tk.Frame):
    def __init__(self, parent, size=16):

        tk.Frame.__init__(self, parent)
        self.canvas = tk.Canvas(self, width=WIDTH_CANVAS_MEMORY, height=HEIGHT_CANVAS_MEMORY)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=tk.TRUE)
        self.scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.FALSE)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', self.on_configure)
        self.frame_inner = tk.Frame(self.canvas)
        self.frame_inner.bind('<Configure>', self.on_configure)
        self.canvas.create_window(0, 0, window=self.frame_inner, anchor=tk.NW)
        self.mem = []
        
        self.label_addr = tk.Label(self.frame_inner, text='Addr', width=WIDTH_LABEL_SHORT)
        self.label_addr.grid(row=0, column=0)
        self.label_value = tk.Label(self.frame_inner, text='Value', width=WIDTH_LABEL_LONG)
        self.label_value.grid(row=0, column=1)
        for i in range(size):
            label_addr = tk.Label(self.frame_inner, text=str(i), width=WIDTH_LABEL_SHORT)
            label_addr.grid(row=i+1, column=0)
            label_value = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_value.grid(row=i+1, column=1)
            self.mem.append([label_addr, label_value])
        for i in range(2):
            self.grid_columnconfigure(i, weight=1)
    
    def refresh(self, memory):
        for i, word in enumerate(self.mem):
            word[1].configure(text=str(memory[i]))
    
    def resize(self, size):
        if len(self.mem) < size:
            for i in range(len(self.mem), size):
                label_addr = tk.Label(self.frame_inner, text=str(i), width=WIDTH_LABEL_SHORT)
                label_addr.grid(row=i+1, column=0)
                label_value = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
                label_value.grid(row=i+1, column=1)
                self.mem.append([label_addr, label_value])
        else:
            for i in range(len(self.mem), size, -1):
                word = self.mem.pop(i-1)
                word[0].destroy()
                word[1].destroy()

    def on_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox(tk.ALL))

class ROBFrame(tk.Frame):
    def __init__(self, parent, num_entries=16): 

        tk.Frame.__init__(self, parent)
        self.canvas = tk.Canvas(self, width=WIDTH_CANVAS_ROB, height=HEIGHT_CANVAS_ROB)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=tk.TRUE)
        self.scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.FALSE)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', self.on_configure)
        self.frame_inner = tk.Frame(self.canvas)
        self.frame_inner.bind('<Configure>', self.on_configure)
        self.canvas.create_window(0, 0, window=self.frame_inner, anchor=tk.NW)
        self.rob = []
        self.ptr = []
        self.head = 0
        self.tail = -1
        for i in range(num_entries + 1):
            label_ptr = tk.Label(self.frame_inner, width=WIDTH_LABEL_LONG)
            label_ptr.grid(row=i, column=0)
            self.ptr.append(label_ptr)
        self.label_index = tk.Label(self.frame_inner, text='Index', width=WIDTH_LABEL_SHORT)
        self.label_index.grid(row=0, column=1)
        self.label_busy = tk.Label(self.frame_inner, text='Busy', width=WIDTH_LABEL_SHORT)
        self.label_busy.grid(row=0, column=2)
        self.label_instr = tk.Label(self.frame_inner, text='Instr', width=WIDTH_LABEL_LONG)
        self.label_instr.grid(row=0, column=3)
        self.label_state = tk.Label(self.frame_inner, text='State', width=WIDTH_LABEL_MID)
        self.label_state.grid(row=0, column=4)
        self.label_unit = tk.Label(self.frame_inner, text='Unit', width=WIDTH_LABEL_MID)
        self.label_unit.grid(row=0, column=5)
        self.label_valid = tk.Label(self.frame_inner, text='Valid', width=WIDTH_LABEL_SHORT)
        self.label_valid.grid(row=0, column=6)
        self.label_result = tk.Label(self.frame_inner, text='Result', width=WIDTH_LABEL_LONG)
        self.label_result.grid(row=0, column=7)
        self.label_storeaddr = tk.Label(self.frame_inner, text='StoreAddr', width=WIDTH_LABEL_MID)
        self.label_storeaddr.grid(row=0, column=8)
        for i in range(num_entries):
            label_index = tk.Label(self.frame_inner, text=str(i), width=WIDTH_LABEL_SHORT)
            label_index.grid(row=i+1, column=1)
            label_busy = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_busy.grid(row=i+1, column=2)
            label_instr = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_instr.grid(row=i+1, column=3)
            label_state = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_MID)
            label_state.grid(row=i+1, column=4)
            label_unit = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_MID)
            label_unit.grid(row=i+1, column=5)
            label_valid = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_valid.grid(row=i+1, column=6)
            label_result = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_result.grid(row=i+1, column=7)
            label_storeaddr = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_MID)
            label_storeaddr.grid(row=i+1, column=8)
            self.rob.append([label_index, label_busy, label_instr, label_state, label_unit, label_valid, label_result, label_storeaddr])
        for i in range(9):
            self.grid_columnconfigure(i, weight=1)
    
    def refresh(self, reorderBuf, headRB, tailRB):
        for i, entry in enumerate(self.rob):
            entry[1].configure(text=str(reorderBuf[i].busy))
            if reorderBuf[i].busy == 0:
                for field in entry[2:]:
                    field.configure(text='-')
            else:
                entry[2].configure(text=disassemble_line(reorderBuf[i].instr))
                entry[3].configure(text=STATES.get(reorderBuf[i].instrState, 'NULL'))
                entry[4].configure(text=UNITS.get(reorderBuf[i].execUnit, 'NULL'))
                entry[5].configure(text=str(reorderBuf[i].valid))
                entry[6].configure(text=str(reorderBuf[i].result))
                entry[7].configure(text=str(reorderBuf[i].storeAddress))
        self.ptr[self.head+1].configure(text='')
        self.ptr[self.tail+1].configure(text='')
        if headRB == tailRB:
            self.ptr[headRB+1].configure(text='Head & Tail ->')
        else:
            self.ptr[headRB+1].configure(text='Head ->')
            self.ptr[tailRB+1].configure(text='Tail ->')
        self.head = headRB
        self.tail = tailRB
    
    def on_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox(tk.ALL))

class ResFrame(tk.Frame):
    def __init__(self, parent, num_units=6): 

        tk.Frame.__init__(self, parent)
        self.canvas = tk.Canvas(self, width=WIDTH_CANVAS_RES, height=HEIGHT_CANVAS_RES)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=tk.TRUE)
        self.scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.FALSE)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', self.on_configure)
        self.frame_inner = tk.Frame(self.canvas)
        self.frame_inner.bind('<Configure>', self.on_configure)
        self.canvas.create_window(0, 0, window=self.frame_inner, anchor=tk.NW)
        self.res = []
        self.label_name = tk.Label(self.frame_inner, text='Name', width=WIDTH_LABEL_MID)
        self.label_name.grid(row=0, column=0)
        self.label_busy = tk.Label(self.frame_inner, text='Busy', width=WIDTH_LABEL_SHORT)
        self.label_busy.grid(row=0, column=1)
        self.label_instr = tk.Label(self.frame_inner, text='Instr', width=WIDTH_LABEL_LONG)
        self.label_instr.grid(row=0, column=2)
        self.label_vj = tk.Label(self.frame_inner, text='Vj', width=WIDTH_LABEL_LONG)
        self.label_vj.grid(row=0, column=3)
        self.label_vk = tk.Label(self.frame_inner, text='Vk', width=WIDTH_LABEL_LONG)
        self.label_vk.grid(row=0, column=4)
        self.label_qj = tk.Label(self.frame_inner, text='Qj', width=WIDTH_LABEL_SHORT)
        self.label_qj.grid(row=0, column=5)
        self.label_qk = tk.Label(self.frame_inner, text='Qk', width=WIDTH_LABEL_SHORT)
        self.label_qk.grid(row=0, column=6)
        self.label_extimeleft = tk.Label(self.frame_inner, text='ExTimeLeft', width=WIDTH_LABEL_LONG)
        self.label_extimeleft.grid(row=0, column=7)
        self.label_robidx = tk.Label(self.frame_inner, text='ROBidx', width=WIDTH_LABEL_SHORT)
        self.label_robidx.grid(row=0, column=8)
        for i in range(num_units):
            label_name = tk.Label(self.frame_inner, text=UNITS.get(i+1, "NULL"), width=WIDTH_LABEL_MID)
            label_name.grid(row=i+1, column=0)
            label_busy = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_busy.grid(row=i+1, column=1)
            label_instr = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_instr.grid(row=i+1, column=2)
            label_vj = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_vj.grid(row=i+1, column=3)
            label_vk = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_vk.grid(row=i+1, column=4)
            label_qj = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_qj.grid(row=i+1, column=5)
            label_qk = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_qk.grid(row=i+1, column=6)
            label_extimeleft = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_LONG)
            label_extimeleft.grid(row=i+1, column=7)
            label_robidx = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_SHORT)
            label_robidx.grid(row=i+1, column=8)
            self.res.append([label_name, label_busy, label_instr, label_vj, label_vk, label_qj, label_qk, label_extimeleft, label_robidx])
        for i in range(9):
            self.grid_columnconfigure(i, weight=1)
    
    def refresh(self, reservation):
        for i, unit in enumerate(self.res):
            unit[1].configure(text=str(reservation[i].busy))
            if reservation[i].busy == 0:
                for field in unit[2:]:
                    field.configure(text='-')
            else:
                unit[2].configure(text=disassemble_line(reservation[i].instr))
                if reservation[i].Qj < 0:
                    unit[3].configure(text=reservation[i].Vj)
                    unit[5].configure(text='READY')
                else:
                    unit[3].configure(text='NOT READY')
                    unit[5].configure(text=str(reservation[i].Qj))
                if reservation[i].Qk < 0:
                    unit[4].configure(text=reservation[i].Vk)
                    unit[6].configure(text='READY')
                else:
                    unit[4].configure(text='NOT READY')
                    unit[6].configure(text=str(reservation[i].Qk))
                unit[7].configure(text=str(reservation[i].exTimeLeft))
                unit[8].configure(text=str(reservation[i].reorderNum))
    
    def on_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox(tk.ALL))


class TomasuloGUI:

    def __init__(self):
        self.root=tk.Tk()
        self.root.title('Tomasulo Algorithm With Re-order Buffer Visualizer')
        self.root.geometry(WINDOW_SIZE)
        self.root.grid_columnconfigure(0, weight=1)

        self.input_file_path = None

        self.frame_control_bar = tk.Frame(self.root)
        self.frame_control_bar.grid(row=0)
        self.button_load = tk.Button(self.frame_control_bar, text='Load code', command=self.load_input_code)
        self.button_load.grid(row=0, column=0)
        self.button_init = tk.Button(self.frame_control_bar, text='Init', command=self.init_machine_state)
        self.button_init.grid(row=0, column=1)
        self.button_run = tk.Button(self.frame_control_bar, text='Run', command=self.run)
        self.button_run.grid(row=0, column=2)
        self.button_pause = tk.Button(self.frame_control_bar, text='Pause', command=self.pause)
        self.button_pause.grid(row=0, column=3)
        self.button_tick = tk.Button(self.frame_control_bar, text='Tick', command=self.tick)
        self.button_tick.grid(row=0, column=4)
        self.button_back = tk.Button(self.frame_control_bar, text='Back', command=None)
        self.button_back.grid(row=0, column=5)

        self.frame_hint = tk.Frame(self.root)
        self.frame_hint.grid(row=1)
        self.value_path_hint = tk.StringVar()
        self.value_path_hint.set("Load a code file to begin with")
        self.label_path_hint = tk.Label(self.frame_hint, textvariable=self.value_path_hint)
        self.label_path_hint.grid(row=0)

        self.label_rob = tk.Label(self.root, text="Re-order Buffer", pady=YPAD_TITLES)
        self.label_rob.grid(row=2)
        self.frame_rob = ROBFrame(self.root)
        self.frame_rob.grid(row=3)

        self.label_res = tk.Label(self.root, text="Reservation Stations", pady=YPAD_TITLES)
        self.label_res.grid(row=4)
        self.frame_res = ResFrame(self.root)
        self.frame_res.grid(row=5)
        
        self.frame_regfile_and_memory = tk.Frame(self.root)
        self.frame_regfile_and_memory.grid(row=6)
        for i in range(2):
            self.frame_regfile_and_memory.grid_columnconfigure(i, weight=1)

        self.label_regfile = tk.Label(self.frame_regfile_and_memory, text="Regfile", pady=YPAD_TITLES)
        self.label_regfile.grid(row=0, column=0)
        self.frame_regfile = RegfileFrame(self.frame_regfile_and_memory)
        self.frame_regfile.grid(row=1, column=0)
        
        self.label_memory = tk.Label(self.frame_regfile_and_memory, text="Memory", pady=YPAD_TITLES)
        self.label_memory.grid(row=0, column=1)
        self.frame_memory = MemoryFrame(self.frame_regfile_and_memory)
        self.frame_memory.grid(row=1, column=1)

        self.c_lib = ctypes.cdll.LoadLibrary(PATH_SO)
        self.c_init = self.c_lib.init
        self.c_init.argtypes = [POINTER(machineState), c_char_p]

        self.c_tick = self.c_lib.tick
        self.c_tick.argtypes = [POINTER(machineState)]

        self.state = machineState()

        self.ms_per_cycle = MS_PER_CYCLE
        self.ready = False
        self.running = False

        tk.mainloop()
    
    def load_input_code(self):
        self.input_file_path = fd.askopenfilename()
        if self.input_file_path != '':
            self.value_path_hint.set("Current code file: " + self.input_file_path)

    def init_machine_state(self):
        if self.input_file_path != '':
            self.c_init(pointer(self.state), self.input_file_path.encode())
            self.refresh_everything()

    def refresh_everything(self):
        self.frame_regfile.refresh(self.state.regFile, self.state.regResult)
        self.frame_memory.resize(self.state.memorySize)
        self.frame_memory.refresh(self.state.memory)
        self.frame_rob.refresh(self.state.reorderBuf, self.state.headRB, self.state.tailRB)
        self.frame_res.refresh(self.state.reservation)

    def run(self):
        self.running = 1
        self.tick()

    def pause(self):
        self.running = 0

    def tick(self):
        self.c_tick(pointer(self.state))
        self.refresh_everything()
        if self.state.halt == 1:
            self.running = 0
        if self.running:
            self.root.after(self.ms_per_cycle, self.tick)
        


def main():
    gui = TomasuloGUI()


if __name__ == "__main__":
    main()