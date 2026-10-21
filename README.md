# opsleuth

[English](#english) | [繁體中文](#繁體中文)

Recover the opcode order of Lua bytecode whose opcodes were renumbered, then hand standard bytecode to the decompiler you already use.

## English

Some programs ship Lua bytecode built by a modified VM: the opcode numbers are shuffled and the header is altered, so `unluac`, `luadec`, `ljd` and similar tools refuse to read it. Undoing that by hand means reverse engineering the VM every time.

opsleuth infers the mapping automatically for Lua 5.1 and LuaJIT 2.1. The format is detected per file.

**Try it in your browser:** https://zzoraemon043.github.io/opsleuth/ (runs locally with Pyodide, nothing is uploaded).

```
opsleuth detect  scripts/                         # version, header changes
opsleuth solve   scripts/ -o map.json             # infer the opcode mapping
opsleuth apply   scripts/ --map map.json -o fixed/
opsleuth verify  fixed/ [--unluac unluac.jar] [--decompiler "CMD {}"]
```

### How it works

1. **Header repair.** Tries the layouts a chunk can have and keeps the one that parses to the last byte. Changed signatures, version bytes, zeroed size fields and missing headers are reported and fixed.
2. **Native name table (optional).** `--lib libgame.so` scans an ELF or PE file for an array of pointers to opcode names. Its order is the VM's opcode order. Relocations in position independent code are resolved, and tail-merged strings such as `CALL` inside `TAILCALL` are handled.
3. **Structural constraints.** Every opcode has operand rules that real compiler output always follows: constant indexes stay below the constant count, `CLOSURE` points at a real prototype, `GETUPVAL` stays below the upvalue count, comparisons are followed by `JMP`, `FORPREP` and `FORLOOP` jump to each other, every function ends in `RETURN`, `VARARG` only appears in vararg functions, and so on. For LuaJIT the operand kinds (string, number, table, prototype, upvalue, jump), loop instructions that must point at each other with the same base register, and the per-function FFI and bit operator flags are checked the same way. Candidates that break a rule on any instruction are removed, and the rules are propagated across all files.
4. **Learned scoring.** Opcodes that the rules cannot tell apart, mostly the arithmetic group and `UNM`/`NOT`/`LEN`, are scored with a model trained on open source Lua code: operand kinds, constant types, neighbouring instructions and where operands come from and go to. A global assignment picks the best one-to-one mapping, and conflicts with the neighbour rules are resolved by a best-first search over the alternatives.
5. **Verification.** The rewritten files are checked against the same rules and, if you pass `--unluac` (Lua 5.1) or `--decompiler` with any command such as ljd (`{}` is replaced by the file path), decompiled.

Every opcode in `map.json` says how it was decided (`native`, `constraint` or `score`) and, for scored ones, a margin. Low margins are listed so you know what to double check.

### Accuracy

Held-out test: the model never saw the project being solved. Each cell is the number of wrong opcodes out of all opcodes used, summed over three random renumberings.

**Lua 5.1.** Opcodes renumbered over 0 to 63, debug info kept.

| Project | 10 files | 20 | 50 | 100 | whole project |
|---|---|---|---|---|---|
| kong | 4 / 91 | 4 / 99 | 1 / 104 | 4 / 108 | 0 / 114 |
| snabb | 7 / 102 | 1 / 109 | 0 / 113 | 0 / 114 | 0 / 114 |
| hawkthorne-journey | 3 / 94 | 3 / 99 | 4 / 107 | 0 / 111 | 0 / 114 |
| nn | 4 / 92 | 0 / 98 | 0 / 109 | 0 / 112 | 0 / 114 |
| ZeroBraneStudio | 5 / 99 | 0 / 114 | 0 / 114 | 0 / 114 | 0 / 114 |
| luacheck | 2 / 96 | 8 / 106 | 0 / 108 | 0 / 112 | 0 / 114 |
| Penlight | 3 / 103 | 2 / 107 | 3 / 114 | 3 / 114 | 0 / 114 |
| lapis | 1 / 96 | 2 / 101 | 0 / 113 | 0 / 114 | 0 / 114 |
| luarocks | 3 / 97 | 1 / 102 | 1 / 105 | 0 / 112 | 0 / 114 |
| busted | 2 / 90 | 0 / 100 | 0 / 104 | 0 / 105 | 0 / 105 |

**LuaJIT 2.1.** Opcodes renumbered over 0 to 255, files stripped (`luajit -b`), 70 to 80 opcodes used per project.

| Project | 10 files | 20 | 50 | 100 | whole project |
|---|---|---|---|---|---|
| kong | 12 / 170 | 16 / 191 | 10 / 202 | 13 / 209 | 6 / 228 |
| snabb | 21 / 206 | 26 / 216 | 17 / 228 | 4 / 231 | 0 / 234 |
| hawkthorne-journey | 23 / 163 | 29 / 190 | 21 / 212 | 9 / 218 | 6 / 225 |
| nn | 20 / 151 | 21 / 176 | 18 / 204 | 12 / 213 | 12 / 219 |
| ZeroBraneStudio | 12 / 184 | 7 / 208 | 4 / 217 | 6 / 226 | 0 / 228 |
| luacheck | 22 / 173 | 28 / 200 | 15 / 209 | 14 / 227 | 22 / 240 |
| Penlight | 17 / 171 | 14 / 199 | 18 / 219 | 19 / 225 | 12 / 225 |
| lapis | 7 / 169 | 9 / 181 | 3 / 214 | 6 / 222 | 6 / 222 |
| luarocks | 7 / 173 | 8 / 194 | 8 / 201 | 4 / 220 | 0 / 225 |
| busted | 15 / 146 | 17 / 171 | 15 / 186 | 3 / 192 | 3 / 192 |

Reproduce with `bench/eval51.py` and `bench/evaljit.py` after compiling a corpus with stock `luac` 5.1 and LuaJIT 2.1.

For Lua 5.1, solving a whole project gave an exact mapping every time; from about a hundred files it is usually exact. LuaJIT splits each operation into more opcodes (`ADDVN`, `ADDNV`, `ADDVV`, `ISEQS`, `ISNES` and so on), so the statistical part is harder: on a whole project 0 to 7 opcodes stay wrong, almost always variants such as `1 - x` against `1 / x` or `==` against `~=`. In these runs 98% of the wrong LuaJIT opcodes were listed as low confidence. Mistakes still decompile into valid but wrong code, so check every opcode that `solve` lists. With `--lib` (Lua 5.1) or `--known` the result does not depend on guessing.

### Scope

- Lua 5.1 and LuaJIT 2.1 (GC64 or not, stripped or not) with the standard instruction layout.
- `--lib` reads opcode name tables, which Lua 5.1 VMs keep and LuaJIT cores do not.
- Not covered: LuaJIT 2.0, Lua 5.2 to 5.4, encrypted or compressed files, changed instruction field layouts, extra custom opcodes.
- Read [docs/responsible-use.md](docs/responsible-use.md) before use.

### Known bytecode

`solve --known stock/` takes stock `luac` or `luajit -b` output for some of the same scripts (for example a bundled library you can compile yourself). Matching functions are aligned instruction by instruction and fix those opcodes before scoring.

### Install

```
pip install git+https://github.com/zzoraemon043/opsleuth
```

Python 3.10 or newer, no dependencies.

## 繁體中文

有些程式附帶的 Lua 位元碼是用改過的 VM 編譯的：opcode 編號被打亂、檔頭被改，`unluac`、`luadec`、`ljd` 這類工具就讀不了。手動還原得每次都逆向一次 VM。

opsleuth 支援 Lua 5.1 和 LuaJIT 2.1，會逐檔判斷格式、自動推出對應關係，再輸出標準位元碼交給你原本用的反編譯器。

**線上試用：** https://zzoraemon043.github.io/opsleuth/ （用 Pyodide 在瀏覽器內執行，檔案不會上傳）。

```
opsleuth detect  scripts/                         # 判斷版本、檔頭改動
opsleuth solve   scripts/ -o map.json             # 推導 opcode 對應
opsleuth apply   scripts/ --map map.json -o fixed/
opsleuth verify  fixed/ [--unluac unluac.jar] [--decompiler "CMD {}"]
```

### 原理

1. **檔頭修復**：嘗試位元碼可能的各種配置，留下能完整解析到最後一個位元組的那個。簽名、版本位元組被改、大小欄位被清零、整個檔頭被拿掉，都會列出並修好。
2. **原生名稱表（選用）**：`--lib libgame.so` 會在 ELF 或 PE 檔裡找指向 opcode 名稱的指標陣列，陣列順序就是 VM 的 opcode 順序。會處理位置無關程式碼的重定位，以及 `CALL` 被合併進 `TAILCALL` 尾端這種字串共用。
3. **結構約束**：每個 opcode 都有編譯器一定遵守的運算元規則，例如常數索引小於常數數量、`CLOSURE` 指向存在的子函式、比較指令後面一定接 `JMP`、`FORPREP` 和 `FORLOOP` 互相跳轉、每個函式以 `RETURN` 結尾、`VARARG` 只出現在可變參數函式。LuaJIT 另外檢查運算元種類（字串、數字、表、子函式、upvalue、跳躍）、迴圈指令必須互相指向且基底暫存器相同，以及每個函式的 FFI／位元運算旗標。只要有一條指令違反規則，該候選就被排除，並在所有檔案間傳播。
4. **學習評分**：規則分不出來的（多半是四則運算那組和 `UNM`/`NOT`/`LEN`），用開源 Lua 程式碼訓練的模型評分：運算元種類、常數型別、前後指令、運算元從哪來往哪去。最後用全域指派選出最佳的一對一對應；和前後指令規則衝突時，用最佳優先搜尋改選其他候選。
5. **驗證**：改寫後的檔案再用同一套規則檢查；加上 `--unluac`（Lua 5.1）或 `--decompiler`（任何反編譯指令，例如 ljd，`{}` 會換成檔案路徑）會實際反編譯一次。

`map.json` 裡每個 opcode 都寫明怎麼決定的（`native`、`constraint`、`score`），評分決定的會附信心差距，低信心的會另外列出，方便你人工確認。

### 準確度

英文段的兩張表格是「模型沒看過的專案」測試，每格是三次隨機編號加總後，錯誤 opcode 數／用到的 opcode 總數。Lua 5.1 在 0～63 隨機編號並保留除錯資訊；LuaJIT 在 0～255 隨機編號，檔案去除除錯資訊（`luajit -b`）。

- **Lua 5.1**：整個專案一起解時每次都完全正確，檔案數到一百個左右通常也全對。
- **LuaJIT 2.1**：同一種運算拆成更多 opcode（`ADDVN`、`ADDNV`、`ADDVV`、`ISEQS`、`ISNES`…），統計部分比較難。整個專案一起解時會剩 0～7 個錯，幾乎都是 `1 - x` 和 `1 / x`、`==` 和 `~=` 這類變體互換；這些錯誤有 98% 被列為低信心。

錯誤的結果仍能反編譯，但運算子會錯，所以 `solve` 列出的低信心 opcode 要人工確認。有 `--lib`（Lua 5.1）或 `--known` 時結果不需要猜。

### 範圍

- 支援標準指令格式的 Lua 5.1 和 LuaJIT 2.1（GC64 與否、有無除錯資訊皆可）。
- `--lib` 讀的是 opcode 名稱表；Lua 5.1 的 VM 會保留，LuaJIT 核心沒有。
- 不支援：LuaJIT 2.0、Lua 5.2～5.4、加密或壓縮的檔案、指令欄位排列被改、額外自訂的 opcode。
- 使用前請先看 [docs/responsible-use.md](docs/responsible-use.md)。

### 已知位元碼

`solve --known stock/` 可以給部分相同腳本的標準 `luac` 或 `luajit -b` 輸出（例如你自己能編譯的內附函式庫），比對到的函式會逐指令對齊，評分前就先確定這些 opcode。

### 安裝

```
pip install git+https://github.com/zzoraemon043/opsleuth
```

需要 Python 3.10 以上，沒有其他相依套件。

## License

MIT
