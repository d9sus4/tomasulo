#include <stdio.h>
#include <string.h>
#include <cstdlib>

#define MAXLINELENGTH 1000 /* 机器指令的最大长度 */
#define MEMSIZE 10000      /* 内存的最大容量     */
#define NUMREGS 32         /* 寄存器数量         */

/*
 * 操作码和功能码定义
 */

#define regRegALU 0 /* 寄存器-寄存器的ALU运算的操作码为0 */
#define LW 35
#define SW 43
#define ADDI 8
#define ANDI 12
#define BEQZ 4
#define J 2
#define HALT 1
#define NOOP 3
#define addFunc 32 /* ALU运算的功能码 */
#define subFunc 34
#define andFunc 36

#define NOOPINSTRUCTION 0x0c000000

/*
 * 执行单元
 */
#define LOAD1 1
#define LOAD2 2
#define STORE1 3
#define STORE2 4
#define INT1 5
#define INT2 6

#define NUMUNITS 6                                                                 /* 执行单元数量 */
char *unitname[NUMUNITS] = {"LOAD1", "LOAD2", "STORE1", "STORE2", "INT1", "INT2"}; /* 执行单元的名称 */

/*
 * 不同操作所需要的周期数
 */
#define BRANCHEXEC 3 /* 分支操作 */
#define LDEXEC 2     /* Load     */
#define STEXEC 2     /* Store    */
#define INTEXEC 1    /* 整数运算 */

/*
 * 指令状态
 */
#define ISSUING 0                                                              /* 发射   */
#define EXECUTING 1                                                            /* 执行   */
#define WRITINGRESULT 2                                                        /* 写结果 */
#define COMMITTING 3                                                           /* 提交   */
char *statename[4] = {"ISSUING", "EXECUTING", "WRITINGRESULT", "COMMTITTING"}; /*  状态名称 */

#define RBSIZE 16 /* ROB有16个单元 */
#define BTBSIZE 8 /* 分支预测缓冲栈有8个单元 */

/*
 * 2 bit 分支预测状态
 */
#define STRONGNOT 0
#define WEAKTAKEN 1
#define WEAKNOT 2
#define STRONGTAKEN 3

/*
 * 分支跳转结果
 */
#define NOTTAKEN 0
#define TAKEN 1

typedef struct _resStation
{            /* 保留栈的数据结构 */
  int instr; /*    指令    */
  int busy;  /* 空闲标志位 */
  int Vj;    /* Vj, Vk 存放操作数, Vj 存放 Address */
  int Vk;
  int Qj;         /* Qj, Qk 存放将会生成结果的执行单元编号 */
  int Qk;         /* <0 则表示对应的V有效 */
  int exTimeLeft; /* 指令执行的剩余时间 */
  int reorderNum; /* 该指令对应的ROB项编号 */
} resStation;

typedef struct _reorderEntry
{                   /* ROB项的数据结构 */
  int busy;         /* 空闲标志位 */
  int instr;        /* 指令 */
  int execUnit;     /* 执行单元编号 */
  int instrState;  /* 指令的当前状态 */
  int valid;        /* 表明结果是否有效的标志位 */
  int result;       /* 在提交之前临时存放结果 */
  int storeAddress; /* store指令的内存地址 */
} reorderEntry;

typedef struct _regResultEntry
{                 /* 寄存器状态的数据结构 */
  int valid;      /* 1表示寄存器值有效, 否则0 */
  int reorderNum; /* 如果值无效, 记录ROB中哪个项目会提交结果 */
} regResultEntry;

typedef struct _btbEntry
{                   /* 分支预测缓冲栈的数据结构 */
  int valid;        /* 有效位 */
  int branchPC;     /* 分支指令的PC值 */
  int branchTarget; /* when predict taken, update PC with target */
  int branchPred;   /* 预测：2-bit分支历史 */
} btbEntry;

typedef struct _machineState
{                                    /* 虚拟机状态的数据结构 */
  int pc;                            /* PC */
  int cycles;                        /* 已经过的周期数 */
  resStation reservation[NUMUNITS];  /* 保留栈 */
  reorderEntry reorderBuf[RBSIZE];   /* ROB */
  int headRB;
  int tailRB;
  regResultEntry regResult[NUMREGS]; /* 寄存器状态 */
  btbEntry btBuf[BTBSIZE];           /* 分支预测缓冲栈 */
  int memory[MEMSIZE];               /* 内存   */
  int memorySize;
  int regFile[NUMREGS];              /* 寄存器 */
  int halt;
} machineState;

int field0(int);
int field1(int);
int field2(int);
int opcode(int);

void printInstruction(int);

extern "C" {
  void init(machineState *statePtr, char *filename);
  void tick(machineState *statePtr);
}

void printState(machineState *statePtr, int memorySize)
{
  int i;

  printf("Cycles: %d\n", statePtr->cycles);

  printf("\t pc=%d\n", statePtr->pc);

  printf("\t Reservation stations:\n");
  for (i = 0; i < NUMUNITS; i++)
  {
    if (statePtr->reservation[i].busy == 1)
    {
      printf("\t \t Reservation station %d: ", i);
      if (statePtr->reservation[i].Qj < 0)
      {
        printf("Vj = %d ", statePtr->reservation[i].Vj);
      }
      else
      {
        printf("Qj = %d ", statePtr->reservation[i].Qj);
      }
      if (statePtr->reservation[i].Qk < 0)
      {
        printf("Vk = %d ", statePtr->reservation[i].Vk);
      }
      else
      {
        printf("Qk = %d ", statePtr->reservation[i].Qk);
      }
      printf(" ExTimeLeft = %d  RBNum = %d\n",
             statePtr->reservation[i].exTimeLeft,
             statePtr->reservation[i].reorderNum);
    }
  }

  printf("\t Reorder buffers:\n");
  for (i = 0; i < RBSIZE; i++)
  {
    if (statePtr->reorderBuf[i].busy == 1)
    {
      printf("\t \t Reorder buffer %d: ", i);
      printf("instr %d  executionUnit '%s'  state %s  valid %d  result %d storeAddress %d\n",
             statePtr->reorderBuf[i].instr,
             unitname[statePtr->reorderBuf[i].instr, statePtr->reorderBuf[i].execUnit - 1],
             statename[statePtr->reorderBuf[i].instrState],
             statePtr->reorderBuf[i].valid, statePtr->reorderBuf[i].result,
             statePtr->reorderBuf[i].storeAddress);
    }
  }

  printf("\t Register result status:\n");
  for (i = 1; i < NUMREGS; i++)
  {
    if (!statePtr->regResult[i].valid)
    {
      printf("\t \t Register %d: ", i);
      printf("waiting for reorder buffer number %d\n",
             statePtr->regResult[i].reorderNum);
    }
  }

  /*
   * [TODO]如果你实现了动态分支预测, 将这里的注释取消
   */

  /*printf("\t Branch target buffer:\n");
  for (i=0; i<BTBSIZE; i++){
    if (statePtr->btBuf[i].valid){
      printf("\t \t Entry %d: PC=%d, Target=%d, Pred=%d\n",
       i, statePtr->btBuf[i].branchPC, statePtr->btBuf[i].branchTarget,
       statePtr->btBuf[i].branchPred);
   }
  }*/

  printf("\t Memory:\n");
  for (i = 0; i < memorySize; i++)
  {
    printf("\t \t memory[%d] = %d\n", i, statePtr->memory[i]);
  }

  printf("\t Registers:\n");
  for (i = 0; i < NUMREGS; i++)
  {
    printf("\t \t regFile[%d] = %d\n", i, statePtr->regFile[i]);
  }
}

/*
 *这里对指令进行解码，转换成程序可以识别的格式，需要根据指令格式来进行。
 *可以考虑使用高级语言中的位和逻辑运算
 */
int field0(int instruction)
{
  /*
   *返回指令的第一个寄存器RS1
   */
  return (instruction >> 21) & 0b11111;
}

int field1(int instruction)
{
  /*
   *返回指令的第二个寄存器，RS2或者Rd
   */
  return (instruction >> 16) & 0b11111;
}

int field2(int instruction)
{
  /*
   *返回指令的第三个寄存器，Rd
   */
    return (instruction >> 11) & 0b11111;
}

int immediate(int instruction)
{
  /*
   *返回I型指令的立即数部分
   */
  return (instruction << 16) >> 16;
}

int jumpAddr(int instruction)
{
  /*
   *返回J型指令的跳转地址
   */
  return (instruction << 6) >> 6;
}

int opcode(int instruction)
{
  /*
   *返回指令的操作码
   */
  return (instruction >> 26) & 0b111111;
}

int func(int instruction)
{
  /*
   *返回R型指令的功能域
   */
  return instruction & 0b11111111111;
}

void printInstruction(int instr)
{
  char opcodeString[10];
  char funcString[11];
  int funcCode;
  int op;

  if (opcode(instr) == regRegALU)
  {
    funcCode = func(instr);
    if (funcCode == addFunc)
    {
      strcpy(opcodeString, "add");
    }
    else if (funcCode == subFunc)
    {
      strcpy(opcodeString, "sub");
    }
    else if (funcCode == andFunc)
    {
      strcpy(opcodeString, "and");
    }
    else
    {
      strcpy(opcodeString, "alu");
    }
    printf("%s %d %d %d \n", opcodeString, field0(instr), field1(instr),
           field2(instr));
  }
  else if (opcode(instr) == LW)
  {
    strcpy(opcodeString, "lw");
    printf("%s %d %d %d\n", opcodeString, field0(instr), field1(instr),
           immediate(instr));
  }
  else if (opcode(instr) == SW)
  {
    strcpy(opcodeString, "sw");
    printf("%s %d %d %d\n", opcodeString, field0(instr), field1(instr),
           immediate(instr));
  }
  else if (opcode(instr) == ADDI)
  {
    strcpy(opcodeString, "addi");
    printf("%s %d %d %d\n", opcodeString, field0(instr), field1(instr),
           immediate(instr));
  }
  else if (opcode(instr) == ANDI)
  {
    strcpy(opcodeString, "andi");
    printf("%s %d %d %d\n", opcodeString, field0(instr), field1(instr),
           immediate(instr));
  }
  else if (opcode(instr) == BEQZ)
  {
    strcpy(opcodeString, "beqz");
    printf("%s %d %d %d\n", opcodeString, field0(instr), field1(instr),
           immediate(instr));
  }
  else if (opcode(instr) == J)
  {
    strcpy(opcodeString, "j");
    printf("%s %d\n", opcodeString, jumpAddr(instr));
  }
  else if (opcode(instr) == HALT)
  {
    strcpy(opcodeString, "halt");
    printf("%s\n", opcodeString);
  }
  else if (opcode(instr) == NOOP)
  {
    strcpy(opcodeString, "noop");
    printf("%s\n", opcodeString);
  }
  else
  {
    strcpy(opcodeString, "data");
    printf("%s %d\n", opcodeString, instr);
  }
}

int convertNum16(int num)
{
  /* convert an 16 bit number into a 32-bit or 64-bit number */
  if (num & 0x8000)
  {
    num -= 65536;
  }
  return (num);
}

int convertNum26(int num)
{
  /* convert an 26 bit number into a 32-bit or 64-bit number */
  if (num & 0x200000)
  {
    num -= 67108864;
  }
  return (num);
}

void updateRes(int reorderNum, machineState *statePtr, int value)
{
  /*
   * 更新保留栈:
   * 将位于公共数据总线上的数据
   * 复制到正在等待它的其他保留栈中去
   */
  for (int i = 0; i < NUMUNITS; i++) {
    if (statePtr->reservation[i].Qj == reorderNum) {
      statePtr->reservation[i].Vj = value;
      statePtr->reservation[i].Qj = -1;
    }
    if (statePtr->reservation[i].Qk == reorderNum) {
      statePtr->reservation[i].Vk = value;
      statePtr->reservation[i].Qk = -1;
    }
  }
}

void issueInstr(int instr, int unit, machineState *statePtr, int reorderNum)
{

  /*
   * 发射指令:
   * 填写保留栈和ROB项的内容.
   * 注意, 要在所有的字段中写入正确的值.
   * 检查寄存器状态, 相应的在Vj,Vk和Qj,Qk字段中设置正确的值:
   * 对于I类型指令, 设置Qk=0,Vk=0;
   * 对于sw指令, 如果寄存器有效, 将寄存器中的内存基地址保存在Vj中;
   * 对于beqz和j指令, 将当前PC+1的值保存在Vk字段中.
   * 如果指令在提交时会修改寄存器的值, 还需要在这里更新寄存器状态数据结构.
   */
  int op = opcode(instr);
  if (instr == NOOPINSTRUCTION) return;
  if (op == SW) {
    int rs = field0(instr);
    int rd = field1(instr);
    // 填写 ROB
    reorderEntry &robEntry = statePtr->reorderBuf[reorderNum];
    robEntry.busy = 1;
    robEntry.instr = instr;
    robEntry.instrState = ISSUING;
    robEntry.valid = 0;
    robEntry.execUnit = unit;
    // 填写对应运算模块的保留站
    resStation &resEntry = statePtr->reservation[unit-1];
    resEntry.instr = instr;
    resEntry.busy = 1;
    resEntry.reorderNum = reorderNum;
    // 检查 rs1、rs2 寄存器状态
    regResultEntry &rsResultEntry = statePtr->regResult[rs];
    regResultEntry &rdResultEntry = statePtr->regResult[rd];
    if (rsResultEntry.valid) {
      resEntry.Vj = statePtr->regFile[rs];
      resEntry.Qj = -1;
    } else {
      resEntry.Qj = rsResultEntry.reorderNum;
    }
    if (rdResultEntry.valid) {
      resEntry.Vk = statePtr->regFile[rd];
      resEntry.Qk = -1;
    } else {
      resEntry.Qk = rdResultEntry.reorderNum;
    }
  } else if (op == LW || op == ADDI || op == ANDI || op == BEQZ) {
    int rs = field0(instr);
    int rd = field1(instr);
    // 填写 ROB
    reorderEntry &robEntry = statePtr->reorderBuf[reorderNum];
    robEntry.busy = 1;
    robEntry.instr = instr;
    robEntry.instrState = ISSUING;
    robEntry.valid = 0;
    robEntry.execUnit = unit;
    // 填写对应存储/运算模块的保留站
    resStation &resEntry = statePtr->reservation[unit-1];
    resEntry.instr = instr;
    resEntry.busy = 1;
    resEntry.Qk = -1;
    resEntry.Vk = 0;
    resEntry.reorderNum = reorderNum;
    if (op == BEQZ) {
      resEntry.Vk = statePtr->pc + 1;
    }
    // 检查 rs 寄存器状态
    regResultEntry &rsResultEntry = statePtr->regResult[rs];
    if (rsResultEntry.valid) {
      resEntry.Vj = statePtr->regFile[rs];
      resEntry.Qj = -1;
    } else {
      resEntry.Qj = rsResultEntry.reorderNum;
    }
    // 修改 rd 寄存器状态
    regResultEntry &rdResultEntry = statePtr->regResult[rd];
    rdResultEntry.reorderNum = reorderNum;
    rdResultEntry.valid = 0;
  } else if (op == regRegALU) {
    int rs1 = field0(instr);
    int rs2 = field1(instr);
    int rd = field2(instr);
    // 填写 ROB
    reorderEntry &robEntry = statePtr->reorderBuf[reorderNum];
    robEntry.busy = 1;
    robEntry.instr = instr;
    robEntry.instrState = ISSUING;
    robEntry.valid = 0;
    robEntry.execUnit = unit;
    // 填写对应运算模块的保留站
    resStation &resEntry = statePtr->reservation[unit-1];
    resEntry.instr = instr;
    resEntry.busy = 1;
    resEntry.reorderNum = reorderNum;
    // 检查 rs1、rs2 寄存器状态
    regResultEntry &rs1ResultEntry = statePtr->regResult[rs1];
    regResultEntry &rs2ResultEntry = statePtr->regResult[rs2];
    if (rs1ResultEntry.valid) {
      resEntry.Vj = statePtr->regFile[rs1];
      resEntry.Qj = -1;
    } else {
      resEntry.Qj = rs1ResultEntry.reorderNum;
    }
    if (rs2ResultEntry.valid) {
      resEntry.Vk = statePtr->regFile[rs2];
      resEntry.Qk = -1;
    } else {
      resEntry.Qk = rs2ResultEntry.reorderNum;
    }
    // 修改 rd 寄存器状态
    regResultEntry &rdResultEntry = statePtr->regResult[rd];
    rdResultEntry.reorderNum = reorderNum;
    rdResultEntry.valid = 0;
  } else { // jtypes, including halt
    // 填写 ROB
    reorderEntry &robEntry = statePtr->reorderBuf[reorderNum];
    robEntry.busy = 1;
    robEntry.instr = instr;
    robEntry.instrState = ISSUING;
    robEntry.valid = 0;
    robEntry.execUnit = unit;
    // 填写对应运算模块的保留站
    resStation &resEntry = statePtr->reservation[unit-1];
    resEntry.instr = instr;
    resEntry.busy = 1;
    resEntry.reorderNum = reorderNum;
    resEntry.Qj = -1;
    resEntry.Vk = statePtr->pc + 1;
    resEntry.Qk = -1;
  }
}

int checkReorder(machineState *statePtr, int &headRB, int &tailRB)
{
  /*
   * 在ROB的队尾检查是否有空闲的空间, 如果有, 返回空闲项目的编号.
   * ROB是一个循环队列, 它可以容纳RBSIZE个项目.
   * 新的指令被添加到队列的末尾, 指令提交则是从队首进行的.
   * 当队列的首指针或尾指针到达数组中的最后一项时, 它应滚动到数组的第一项.
   */
  if (tailRB == -1) { // empty
    return headRB;
  } else if ((headRB - tailRB) % RBSIZE == 1) {
    return -1; 
  }
  return tailRB + 1;
}

int checkReservation(machineState *statePtr, int instr) {
  /*
   * 查看是否有空闲的保留栈
   */
  int op = opcode(instr);
  if (op == LW) {
    for (int i = 1; i <= 2; i++) {
      if (statePtr->reservation[i-1].busy == 0) return i;
    }
  } else if (op == SW) {
    for (int i = 3; i <= 4; i++) {
      if (statePtr->reservation[i-1].busy == 0) return i;
    }
  } else {
    for (int i = 5; i <= 6; i++) {
      if (statePtr->reservation[i-1].busy == 0) return i;
    }
  }
  return -1;
}

int getResult(resStation rStation, machineState *statePtr)
{
  int op, immed, function, address;

  /*
   * 这个函数负责计算有输出的指令的结果.
   * 你需要完成下面的case语句....
   */

  op = opcode(rStation.instr);
  immed = immediate(rStation.instr);
  function = func(rStation.instr);
  address = jumpAddr(rStation.instr);

  switch (op) {
    case regRegALU:
      switch (function) {
        case addFunc:
          return (rStation.Vj + rStation.Vk);
        case subFunc:
          return (rStation.Vj - rStation.Vk);
        case andFunc:
          return (rStation.Vj & rStation.Vk);
      }
      break;
    case ANDI:
      return (rStation.Vj & immed);
    case ADDI:
      return (rStation.Vj + immed);
    case LW:
      return (statePtr->memory[rStation.Vj + immed]);
    case SW:
      statePtr->reorderBuf[rStation.reorderNum].storeAddress = rStation.Vj + immed;
      return rStation.Vk;
    case J:
      return (rStation.Vk + address);
    case BEQZ:
      if (rStation.Vj == 0) return (rStation.Vk + immed);
      else return -1;
    default:
      break;
  }

  return -1;
}

void init(machineState *statePtr, char *filename) {
  FILE *filePtr;
  int pc, done, instr, i;
  char line[MAXLINELENGTH];
  int success, newBuf, op, unit;
  int regA, regB, immed, address;
  int flush;
  int rbnum;

  filePtr = fopen(filename, "r");

  if (filePtr == NULL)
  {
    printf("error: can't open file %s", filename);
    perror("fopen");
    return;
  }

  // statePtr = (machineState *)malloc(sizeof(machineState));

  for (i = 0; i < MEMSIZE; i++)
  {
    statePtr->memory[i] = 0;
  }
  pc = 16;
  done = 0;
  while (!done)
  {
    if (fgets(line, MAXLINELENGTH, filePtr) == NULL)
    {
      done = 1;
    }
    else
    {
      if (sscanf(line, "%d", &instr) != 1)
      {
        printf("error in reading address %d\n", pc);
        exit(1);
      }

      statePtr->memory[pc] = instr;
      printf("memory[%d]=%d\n", pc, statePtr->memory[pc]);
      pc = pc + 1;
    }
  }

  statePtr->memorySize = pc;
  statePtr->halt = 0;

  /*
   * 状态初始化
   */

  statePtr->pc = 16;
  statePtr->cycles = 0;
  for (i = 0; i < NUMREGS; i++)
  {
    statePtr->regFile[i] = 0;
  }
  for (i = 0; i < NUMUNITS; i++)
  {
    statePtr->reservation[i].busy = 0;
  }
  for (i = 0; i < RBSIZE; i++)
  {
    statePtr->reorderBuf[i].busy = 0;
  }

  statePtr->headRB = 0;
  statePtr->tailRB = -1;

  for (i = 0; i < NUMREGS; i++)
  {
    statePtr->regResult[i].valid = 1;
  }
  for (i = 0; i < BTBSIZE; i++)
  {
    statePtr->btBuf[i].valid = 0;
  }

  return;
}

void tick(machineState *statePtr) {
  
  if (statePtr->halt == 1) return;

  /*
   * 处理指令
   */

  /* 执行一个循环:在执行halt指令时设置halt=1 */

  /*
    * 基本要求:
    * 首先, 确定是否需要清空流水线或提交位于ROB的队首的指令.
    * 我们处理分支跳转的缺省方法是假设跳转不成功, 如果我们的预测是错误的,
    * 就需要清空流水线(ROB/保留栈/寄存器状态), 设置新的pc = 跳转目标.
    * 如果不需要清空, 并且队首指令能够提交, 在这里更新状态:
    *     对寄存器访问, 修改寄存器;
    *     对内存写操作, 修改内存.
    * 在完成清空或提交操作后, 不要忘了释放保留栈并更新队列的首指针.
    */
  if (statePtr->tailRB >= 0 && statePtr->reorderBuf[statePtr->headRB].instrState == COMMITTING) {
    reorderEntry &robEntry = statePtr->reorderBuf[statePtr->headRB];
    int op = opcode(robEntry.instr);
    int result = robEntry.result;
    updateRes(statePtr->headRB, statePtr, result);
    // NOOP won't actually issue so don't consider it
    if (op == HALT) {
      printf("i'm halting!!!!!!!!!\n");
      statePtr->halt = 1;
      return;
    } else if (op == J || op == BEQZ) { // JUMP
      if (result >= 0) {
        statePtr->pc = result;
        // CLEAR EVERYTHING
        statePtr->tailRB = statePtr->headRB;
        for (int i = 0; i < RBSIZE; i ++) {
          statePtr->reorderBuf[i].busy = 0;
        }
        for (int i = 0; i < NUMUNITS; i++) {
          statePtr->reservation[i].busy = 0;
        }
        for (int i = 0; i < NUMREGS; i++) {
          statePtr->regResult[i].valid = 1;
        }
      }
    } else if (op == SW) { // WRITE MEMORY
      statePtr->memory[robEntry.storeAddress] = robEntry.result;
    } else { // WRITE BACK
      for (int i = 0; i < NUMREGS; i++) {
        if (statePtr->regResult[i].valid == 0 && statePtr->regResult[i].reorderNum == statePtr->headRB) {
          statePtr->regResult[i].valid = 1;
          statePtr->regFile[i] = robEntry.result;
        }
      }
    }
    statePtr->reorderBuf[statePtr->headRB].busy = 0;
    if (statePtr->headRB == statePtr->tailRB) {
      statePtr->headRB = 0;
      statePtr->tailRB = -1;
    } else {
      statePtr->headRB += 1;
    }
    printf("instr commit finished!!!!! instr = %d, result = %d\n", robEntry.instr, robEntry.result);
  }
  /*
    * 提交完成.
    * 检查所有保留栈中的指令, 对下列状态, 分别完成所需的操作:
    */

  /*
    * 对Writing Result状态:
    * 将结果复制到正在等待该结果的其他保留栈中去;
    * 还需要将结果保存在ROB中的临时存储区中.
    * 释放指令占用的保留栈, 将指令状态修改为Committing
    */

  /*
    * 对Executing状态:
    * 执行剩余时间递减;
    * 在执行完成时, 将指令状态修改为Writing Result
    */

  /*
    * 对Issuing状态:
    * 检查两个操作数是否都已经准备好, 如果是, 将指令状态修改为Executing
    */

  for (int i = 0; i < NUMUNITS; i++) {
    resStation &resEntry = statePtr->reservation[i];
    if (resEntry.busy == 1) {
      reorderEntry &robEntry = statePtr->reorderBuf[resEntry.reorderNum];
      if (robEntry.instrState == WRITINGRESULT) {
        int result = getResult(resEntry, statePtr);
        updateRes(resEntry.reorderNum, statePtr, result);
        robEntry.result = result;
        printf("committing new instr!!!!! instr = %d, result = %d, unit = %d, reorderNum = %d\n", resEntry.instr, result, i+1, resEntry.reorderNum);
        robEntry.instrState = COMMITTING;
        resEntry.busy = 0;
      } else if (robEntry.instrState == EXECUTING) {
        resEntry.exTimeLeft -= 1;
        if (resEntry.exTimeLeft == 0) {
          printf("writing new instr!!!!! instr = %d, unit = %d\n", resEntry.instr, i+1);
          robEntry.instrState = WRITINGRESULT;
        }
      } else if (robEntry.instrState == ISSUING) {
        if (resEntry.Qj < 0 && resEntry.Qk < 0) {
          int op = opcode(resEntry.instr);
          if (op == BEQZ) {
            resEntry.exTimeLeft = BRANCHEXEC;
          } else if (op == LW) {
            resEntry.exTimeLeft = LDEXEC;
          } else if (op == SW) {
            resEntry.exTimeLeft = STEXEC;
          } else {
            resEntry.exTimeLeft = INTEXEC;
          }
          printf("executing new instr!!!!! instr = %d, unit = %d, Vj = %d, Vk = %d, extime = %d\n", resEntry.instr, i+1, resEntry.Vj, resEntry.Vk, resEntry.exTimeLeft);
          robEntry.instrState = EXECUTING;
        }
      }
    }
  }

  /*
    * 最后, 当我们处理完了保留栈中的所有指令后, 检查是否能够发射一条新的指令.
    * 首先检查是否有空闲的保留栈, 如果有, 再检查ROB中是否有空闲的空间,
    * 如果也能找到空闲空间, 发射指令.
    */
  if (statePtr->pc < statePtr->memorySize) {
    int instr = statePtr->memory[statePtr->pc];
    int unit = checkReservation(statePtr, instr);
    int reorderNum = checkReorder(statePtr, statePtr->headRB, statePtr->tailRB);
    printf("trying issuing instr = %d, unit = %d, reorderNum = %d\n", instr, unit, reorderNum);
    if (unit >= 0 && reorderNum >= 0) {
      printf("issuing new instr!!!!! instr = %d, unit = %d, reorderNum = %d\n", instr, unit, reorderNum);
      issueInstr(instr, unit, statePtr, reorderNum);
      statePtr->tailRB += 1;
      statePtr->tailRB %= RBSIZE;
      statePtr->pc += 1;
    }
  }

  /*
    * 周期计数加1
    */

  statePtr->cycles += 1;
  return;
}