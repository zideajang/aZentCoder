# aZentCoder
开发一个会写代码的 Agent


- ​`r"..."`:  这里 r 是 Python 中的 raw 字符串标记，意味着把反斜杠作为普通字符

- `[ \t]*(\w+)?[ \t]*\r?\n`: 这部分匹配 Markdown 代码块的开始。是代码块的起始标记。`[ \t]*` 匹配任意数量的空格或制表符（如果有的话
- `(\w+)? ` 用于匹配表示语言的文本（比如代码块中的 python）

- `\r?\n` 用于匹配换行束符，这样写的好处是兼容 Unix（\n）和 Windows（\r\n）风格

- `(.*?)`: 这是一个非贪婪匹配，可以匹配任意字符序列，代码块中的实际代码。非贪婪意味着会匹配尽可能短的字符串

- `\r?\n[ \t]*``` `: 用于分匹配代码块的结束


与开始模式相似，但顺序相反，确保匹配 Markdown 代码块的结束。