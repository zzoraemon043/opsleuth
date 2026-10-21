# opsleuth

[English](#english) | [繁體中文](#繁體中文)

Recover the opcode order of Lua bytecode whose opcodes were renumbered, then hand standard bytecode to the decompiler you already use.

## English

Some programs ship Lua bytecode built by a modified VM: the opcode numbers are shuffled and the header is altered, so `unluac`, `luadec` and similar tools refuse to read it. Undoing that by hand means reverse engineering the VM every time.

opsleuth infers the mapping automatically.

```
opsleuth detect  scripts/                         # version, header changes
opsleuth solve   scripts/ -o map.json             # infer the opcode mapping
opsleuth apply   scripts/ --map map.json -o fixed/
opsleuth verify  fixed/ [--unluac unluac.jar]
```

### How it works

1. **Header repair.** Tries the layouts a Lua 5.1 chunk can have and keeps the one that parses to the last byte. Changed signatures, version bytes, zeroed size fields and missing headers are reported and fixed.
2. **Native name table (optional).** `--lib libgame.so` scans an ELF or PE file for an array of pointers to opcode names. Its order is the VM's opcode order. Relocations in position independent code are resolved, and tail-merged strings such as `CALL` inside `TAILCALL` are handled.
3. **Structural constraints.** Every opcode has operand rules that real compiler output always follows: constant indexes stay below the constant count, `CLOSURE` points at a real prototype, `GETUPVAL` stays below the upvalue count, comparisons are followed by `JMP`, `FORPREP` and `FORLOOP` jump to each other, every function ends in `RETURN`, `VARARG` only appears in vararg functions, and so on. Candidates that break a rule on any instruction are removed, and the rules are propagated across all files.
4. **Learned scoring.** Opcodes that the rules cannot tell apart, mostly the arithmetic group and `UNM`/`NOT`/`LEN`, are scored with a model trained on open source Lua code: operand kinds, constant types, neighbouring instructions and where operands come from and go to. A global assignment picks the best one-to-one mapping.
5. **Verification.** The rewritten files are checked against the same rules and, if you pass `--unluac`, decompiled.

Every opcode in `map.json` says how it was decided (`native`, `constraint` or `score`) and, for scored ones, a margin. Low margins are listed so you know what to double check.

### Accuracy

Held-out test: the model never saw the project being solved. Opcodes were renumbered at random over 0 to 63 and debug info was kept. Each cell is the number of wrong opcodes out of all opcodes used, summed over three random renumberings.

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

Reproduce with `bench/eval51.py` after compiling a corpus with stock `luac` 5.1.

Solving a whole project gave an exact mapping every time; from about a hundred files it is usually exact. Remaining mistakes are swaps inside the arithmetic group, which still decompile into valid but wrong code, so check any operator that `solve` lists as low confidence. With `--lib` the result comes straight from the VM and needs no guessing.

### Scope

- Lua 5.1 with the standard instruction layout. LuaJIT 2.x is next.
- Not covered: encrypted or compressed files, changed instruction field layouts, extra custom opcodes.
- Read [docs/responsible-use.md](docs/responsible-use.md) before use.

### Known bytecode

`solve --known stock/` takes stock `luac` output for some of the same scripts (for example a bundled library you can compile yourself). Matching functions are aligned instruction by instruction and fix those opcodes before scoring.

### Install

```
pip install git+https://github.com/zzoraemon043/opsleuth
```

Python 3.10 or newer, no dependencies.

## 繁體中文

有些程式附帶的 Lua 位元碼是用改過的 VM 編譯的：opcode 編號被打亂、檔頭被改，`unluac`、`luadec` 這類工具就讀不了。手動還原得每次都逆向一次 VM。

opsleuth 會自動推出對應關係，再輸出標準位元碼交給你原本用的反編譯器。

```
opsleuth detect  scripts/                         # 判斷版本、檔頭改動
opsleuth solve   scripts/ -o map.json             # 推導 opcode 對應
opsleuth apply   scripts/ --map map.json -o fixed/
opsleuth verify  fixed/ [--unluac unluac.jar]
```

### 原理

1. **檔頭修復**：嘗試 Lua 5.1 可能的各種配置，留下能完整解析到最後一個位元組的那個。簽名、版本位元組被改、大小欄位被清零、整個檔頭被拿掉，都會列出並修好。
2. **原生名稱表（選用）**：`--lib libgame.so` 會在 ELF 或 PE 檔裡找指向 opcode 名稱的指標陣列，陣列順序就是 VM 的 opcode 順序。會處理位置無關程式碼的重定位，以及 `CALL` 被合併進 `TAILCALL` 尾端這種字串共用。
3. **結構約束**：每個 opcode 都有編譯器一定遵守的運算元規則，例如常數索引小於常數數量、`CLOSURE` 指向存在的子函式、比較指令後面一定接 `JMP`、`FORPREP` 和 `FORLOOP` 互相跳轉、每個函式以 `RETURN` 結尾、`VARARG` 只出現在可變參數函式。只要有一條指令違反規則，該候選就被排除，並在所有檔案間傳播。
4. **學習評分**：規則分不出來的（多半是四則運算那組和 `UNM`/`NOT`/`LEN`），用開源 Lua 程式碼訓練的模型評分：運算元種類、常數型別、前後指令、運算元從哪來往哪去。最後用全域指派選出最佳的一對一對應。
5. **驗證**：改寫後的檔案再用同一套規則檢查；加上 `--unluac` 會實際反編譯一次。

`map.json` 裡每個 opcode 都寫明怎麼決定的（`native`、`constraint`、`score`），評分決定的會附信心差距，低信心的會另外列出，方便你人工確認。

### 準確度

英文段的表格是「模型沒看過的專案」測試：opcode 在 0～63 隨機重新編號，每格是三次隨機編號加總後，錯誤 opcode 數／用到的 opcode 總數。

整個專案一起解時每次都完全正確，檔案數到一百個左右通常也全對。剩下的錯誤是四則運算彼此對調，反編譯出來語法正確但運算子錯，所以 `solve` 標為低信心的運算子要人工確認。有 `--lib` 時結果直接來自 VM，不需要猜。

### 範圍

- 支援標準指令格式的 Lua 5.1，下一步是 LuaJIT 2.x。
- 不支援：加密或壓縮的檔案、指令欄位排列被改、額外自訂的 opcode。
- 使用前請先看 [docs/responsible-use.md](docs/responsible-use.md)。

### 已知位元碼

`solve --known stock/` 可以給部分相同腳本的標準 `luac` 輸出（例如你自己能編譯的內附函式庫），比對到的函式會逐指令對齊，評分前就先確定這些 opcode。

### 安裝

```
pip install git+https://github.com/zzoraemon043/opsleuth
```

需要 Python 3.10 以上，沒有其他相依套件。

## License

MIT
