import pkgutil

import quantlab

print(f"quantlab {quantlab.__version__}")
for mod in pkgutil.iter_modules(quantlab.__path__):
    if mod.ispkg:
        print(f"  - quantlab.{mod.name}")
