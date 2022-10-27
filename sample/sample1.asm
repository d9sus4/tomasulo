     addi r7,r7,1     ;set r7=1
     addi r1,r1,10    ;set r1=10, r1 is counter
loop add r8,r8,r7     ;r8 = r7+r8
     add r7,r7,r1    ;r10 = r8+r9
     sw r8,r2,0      ;store r8, use r2 as offset
     addi r2,r2,1     ;offset ++
     addi r1,r1,-1    ;counter --
     beqz r1,end      ;loop
     j loop
end halt