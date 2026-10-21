# Responsible use

opsleuth is a research and interoperability tool. It rewrites the opcode numbers of Lua bytecode you already have, so that standard tools can read it again.

## What it does

- Reads Lua 5.1 and LuaJIT 2.1 bytecode files and repairs headers that were changed in simple ways.
- Infers which renumbered opcode corresponds to which standard opcode.
- Reads opcode name tables that a native library already contains in plain form.
- Writes standard bytecode for an existing decompiler.

## What it does not do

- It does not decrypt files. If your files are encrypted or compressed, they are out of scope.
- It does not search for keys, bypass licence checks, anti-cheat or any other protection.
- It does not ship bytecode, keys or recovered sources from any product.

## Before you use it

Check that you have the right to analyse the files you feed it. Laws on reverse engineering differ between countries and so do licence terms. Typical legitimate uses include recovering your own lost sources, studying a format for interoperability, security research and teaching.

## Contributions

Pull requests must keep to the same limits. Test data must be compiled from sources that live in this repository.

---

# 負責任使用

opsleuth 是研究與互通用的工具：把你手上 Lua 位元碼被改過的 opcode 編號改回標準編號，讓現有工具可以再讀。

## 會做的事

- 讀取 Lua 5.1 與 LuaJIT 2.1 位元碼，修復被簡單改動的檔頭。
- 推導被重新編號的 opcode 各自對應哪個標準 opcode。
- 讀取原生程式庫裡本來就以明文存在的 opcode 名稱表。
- 輸出標準位元碼，交給現有的反編譯器。

## 不會做的事

- 不解密。加密或壓縮過的檔案不在範圍內。
- 不搜尋金鑰，不繞過授權檢查、反作弊或任何保護機制。
- 不附帶任何產品的位元碼、金鑰或還原後的源碼。

## 使用前

請確認你有權分析這些檔案。各國對逆向工程的規定不同，授權條款也不同。常見的正當用途包括：找回自己遺失的源碼、為了互通研究格式、資安研究與教學。

## 貢獻

Pull request 也必須遵守同樣的限制。測試資料一律從本倉庫內的源碼編譯。
