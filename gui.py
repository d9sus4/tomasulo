from platform import machine
import tkinter as tk
from tkinter import filedialog as fd
import ctypes
from ctypes import *
import time

SIZE_ROB = 16

WIDTH_CANVAS_REGFILE = 250
HEIGHT_CANVAS_REGFILE = 300

WIDTH_LABEL_REGNAME = 5
WIDTH_LABEL_REGVAL = 10
WIDTH_LABEL_REGVALID = 5
WIDTH_LABEL_REGROBIDX = 5

MS_PER_CYCLE = 100

PATH_SO = "./bin/libtomasulo.so"


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
        ("instrStatus", c_int),
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
        ("btFuf", btbEntry*8),
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
        self.canvas.create_window(0, 0, window=self.frame_inner, anchor=tk.NW)
        self.regs = []
        
        self.label_name = tk.Label(self.frame_inner, text='Name', width=WIDTH_LABEL_REGNAME)
        self.label_name.grid(row=0, column=0)
        self.label_value = tk.Label(self.frame_inner, text='Value', width=WIDTH_LABEL_REGVAL)
        self.label_value.grid(row=0, column=1)
        self.label_valid = tk.Label(self.frame_inner, text='Valid', width=WIDTH_LABEL_REGVALID)
        self.label_valid.grid(row=0, column=2)
        self.label_rob_idx = tk.Label(self.frame_inner, text='ROBidx', width=WIDTH_LABEL_REGROBIDX)
        self.label_rob_idx.grid(row=0, column=3)
        for i in range(num_regs):
            label_name = tk.Label(self.frame_inner, text='r'+str(i), width=WIDTH_LABEL_REGNAME)
            label_name.grid(row=i+1, column=0)
            label_value = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_REGVAL)
            label_value.grid(row=i+1, column=1)
            label_valid = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_REGVALID)
            label_valid.grid(row=i+1, column=2)
            label_rob_idx = tk.Label(self.frame_inner, background='white', bd='0', width=WIDTH_LABEL_REGROBIDX)
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

class TomasuloGUI:

    def __init__(self):
        self.root=tk.Tk()
        self.root.title('Tomasulo Algorithm With Re-order Buffer Visualizer')
        self.root.geometry('600x640')
        self.root.grid_columnconfigure(0, weight=1)

        self.input_file_path = None

        self.frame_control_bar = tk.Frame(self.root)
        self.frame_control_bar.grid(row=0)
        self.button_browse = tk.Button(self.frame_control_bar, text='Load code', command=self.browse_input_code)
        self.button_browse.grid(row=0, column=0)
        self.button_init = tk.Button(self.frame_control_bar, text='Init', command=self.init_machine_state)
        self.button_init.grid(row=0, column=1)
        self.button_start = tk.Button(self.frame_control_bar, text='Start', command=self.start_running)
        self.button_start.grid(row=0, column=2)
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

        self.frame_regfile = RegfileFrame(self.root)
        self.frame_regfile.grid(row=2)

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
    
    def browse_input_code(self):
        self.input_file_path = fd.askopenfilename()
        if self.input_file_path != '':
            self.value_path_hint.set("Current code file: " + self.input_file_path)

    def init_machine_state(self):
        self.c_init(pointer(self.state), self.input_file_path.encode())
        self.refresh_everything()

    def refresh_everything(self):
        self.frame_regfile.refresh(self.state.regFile, self.state.regResult)

    def start_running(self):
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