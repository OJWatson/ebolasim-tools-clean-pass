# Parameter files

Legacy parameter files use bracketed names followed by text values.

```text
[Number of realisations]
1
```

Python:

```python
from ebolasim_tools import ParameterSet

params = ParameterSet.read("p_188.txt")
params["Number of realisations"] = 1
params.write("p_188_debug.txt")
```
