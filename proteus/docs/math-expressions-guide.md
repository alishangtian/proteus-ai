# 数学表达式支持指南

## 概述

Proteus AI 现在支持在**最终结果**的 Markdown 渲染中使用数学表达式。我们使用 KaTeX 库来渲染数学公式。

**注意**: 数学表达式渲染仅在 Agent 的最终完成结果(agent_complete/agent_completed 事件)中生效,工具执行结果等中间过程不会渲染数学表达式。

## 支持的语法

### 行内公式

使用单个 `$` 符号包裹行内数学表达式:

```
这是一个行内公式: $E = mc^2$
```

渲染效果: 这是一个行内公式: $E = mc^2$

### 块级公式

使用双 `$$` 符号包裹块级数学表达式:

```
$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$
```

渲染效果:
$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

### LaTeX 语法

也支持 LaTeX 标准语法:

- 行内: `\( ... \)`
- 块级: `\[ ... \]`

## 示例

### 1. 基础数学公式

```
勾股定理: $a^2 + b^2 = c^2$
```

### 2. 分数和根式

```
二次公式: $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$
```

### 3. 求和与积分

```
$$
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}
$$

$$
\int_0^1 x^2 dx = \frac{1}{3}
$$
```

### 4. 矩阵

```
$$
\begin{bmatrix}
a & b \\
c & d
\end{bmatrix}
$$
```

### 5. 希腊字母

```
常用希腊字母: $\alpha, \beta, \gamma, \Delta, \Sigma, \pi, \theta$
```

### 6. 复杂公式

```
$$
f(x) = \begin{cases}
x^2 & \text{if } x \geq 0 \\
-x^2 & \text{if } x < 0
\end{cases}
$$
```

## 技术实现

- **渲染库**: KaTeX v0.16.9
- **CDN**: jsdelivr
- **自动渲染**: 所有 Markdown 内容在渲染后会自动处理数学表达式
- **错误处理**: 如果公式语法错误,会以红色显示错误信息

## 注意事项

1. 确保数学表达式语法正确,否则可能无法正确渲染
2. 在 Markdown 代码块中的数学表达式不会被渲染
3. 使用 `$` 符号时,如果不是数学表达式,请使用转义: `\$`

## 更多资源

- [KaTeX 支持的函数列表](https://katex.org/docs/supported.html)
- [KaTeX 文档](https://katex.org/docs/api.html)