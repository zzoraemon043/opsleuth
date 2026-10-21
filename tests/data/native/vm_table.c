#include <stdio.h>
#include <string.h>

static const char *const decoy[] = {"MOVE", "JMP", "CALL", NULL};

const char *const opnames_table[] = {
  "TEST",
  "VARARG",
  "CLOSURE",
  "GETUPVAL",
  "NOT",
  "TESTSET",
  "SETTABLE",
  "LEN",
  "NEWTABLE",
  "SETLIST",
  "LOADBOOL",
  "CONCAT",
  "LT",
  "EQ",
  "MUL",
  "CLOSE",
  "SETUPVAL",
  "SUB",
  "GETTABLE",
  "MOVE",
  "LE",
  "UNM",
  "RETURN",
  "POW",
  "ADD",
  "SETGLOBAL",
  "FORPREP",
  "SELF",
  "FORLOOP",
  "GETGLOBAL",
  "CALL",
  "LOADNIL",
  "DIV",
  "TAILCALL",
  "LOADK",
  "TFORLOOP",
  "JMP",
  "MOD",
  NULL
};

int main(int argc, char **argv) {
  int i;
  const char *const *t = argc > 5 ? decoy : opnames_table;
  for (i = 0; t[i] != NULL; i++) {
    if (argc > 1 && strcmp(argv[1], t[i]) == 0) printf("%d %s", i, t[i]);
  }
  return 0;
}
