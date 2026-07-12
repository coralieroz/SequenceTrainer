import random
import sys

def user_input(sequence):
    m=len(sequence); prefix=''.join(f'{float(sequence[i])}, ' for i in range(m-1)) + '?'
    print(prefix,end='\b')                           
    ans=input()
    while not ans.strip():                                      # Prevents user from just pressing 'enter'.
        sys.stdout.write(f"\033[F\033[{len(prefix)-1}C")
        sys.stdout.flush()
        ans=input()
    col=len(prefix)+len(ans)-1
    try:                         
        mark='✅' if float(ans)==sequence[-1] else '❌'
    except:
        mark='❌'
    sys.stdout.write(f"\033[F\033[{col}C {mark}\n")   
    sys.stdout.flush()

def arithmetic(m):
    # an=a0+nd
    a0=random.randint(-20,50); d=random.randint(-12,12)
    while d==0: d=random.randint(-12,12)
    sequence=[a0]
    for i in range(m-1): sequence.append(sequence[i]+d)
    return sequence
    
def geometric(m):
    # an=a0.r^n
    a0=random.randint(1,12); r=random.choice([2,3,1/2,-2])
    if r==0.5: a0=random.randint(1,12)*2**(m-1)                 # Avoids totally crazy answers
    sequence=[a0*r**i for i in range(m)]
    return sequence

def quadratic(m):
    # an=An^2+Bn+C
    A=random.randint(1,4); B=random.randint(-5,5); C=random.randint(-5,10)
    sequence=[A*i*i+B*i+C for i in range(m)]
    return(sequence)

def fibonacci(m):
    # an=k(n-1)+(n-2)
    a0=random.randint(1,8); a1=random.randint(1,8); k=random.choice([-1,1,2,3])
    sequence=[a0,a1]
    for i in range(m-2): sequence.append(k*sequence[i+1]+sequence[i])
    return sequence

def interleaved(m):
    # E.g. 2,3,7,6,12,17,24 which is arithmetic + geometric (alternating)
    i=0; sequences=[]
    while i<2:
        decider=random.random()
        if decider<0.45:
            seq=arithmetic((m+i)//2)
        elif (decider>=0.45 and decider<0.9):
            seq=geometric((m+i)//2)
        elif (decider>0.9 and decider<=0.95):
            seq=quadratic((m+i)//2)
        else:
            seq=fibonacci((m+i)//2)
        sequences.append(seq)
        i+=1
    interleaved=[]
    for j in range(len(sequences[1])):
        interleaved.append(sequences[1][j])
        if j<len(sequences[0]):
            interleaved.append(sequences[0][j])
    return interleaved
        
def mixed(m):
    # E.g. 1,2,5,10,13,26,29 which is a mix of multiplication + addition (alternating)
    def make_op():
        if random.random()<0.5:            # Addition
            c=random.randint(-50,50)
            while c==0: c=random.randint(-50,50)
            return lambda x: x+c
        else:                               # Multiplication
            c=random.randint(-5,5)
            while c==0: c=random.randint(-5,5)
            return lambda x: x*c
    ops=[make_op(),make_op()]
    sequence=[random.randrange(-50,50)]
    for i in range(m-1):
        sequence.append(ops[i%2](sequence[i]))
    return sequence
                
m=9                                 # Deterimne length of sequences (in case of interleaved quadratic, m=9 is right choice).
N=10; t=0                           # Determine number of questions.
while t<N:
    decider=random.randint(0,5)
    if decider==0:
        seq=arithmetic(m)
    elif decider==1:
        seq=geometric(m)
    elif decider==2:
        seq=quadratic(m)
    elif decider==3:
        seq=fibonacci(m)
    elif decider==4:
        seq=interleaved(m)
    else:
        seq=mixed(m)
    user_input(seq)
    t+=1

