# Invoke from the pinned ABC source directory with GNU make and MSYS2 UCRT64.
ABC_MAKE_NO_DEPS := 1
ABC_USE_STDINT_H := 1
ABC_USE_NO_PTHREADS := 1
ABC_USE_NO_READLINE := 1
OPTFLAGS := -O2 -DWIN32_NO_DLL -DSIZEOF_VOID_P=8 -DSIZEOF_LONG=4 -DSIZEOF_INT=4
include Makefile
CC := gcc -std=gnu11
src/aig/gia/giaMan.o: INCLUDES += -include math.h

# A response file avoids the Windows command-line length limit at link time.
abc.exe: $(OBJ)
	$(file >abc-win-objects.rsp,$^)
	$(LD) -o $@ @abc-win-objects.rsp -lm -lws2_32 -lpsapi -lshlwapi
