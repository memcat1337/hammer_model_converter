ENG (google translator):

# hammer model converter

GUI wrapper for two Python converters:

- obj_to_vmf_brushes.py
- obj_to_vmf_triangles.py

## Installation

```bat
python -m pip install -r requirements.txt
```

## Folder structure

All files should be located next to each other:

```text
hammer_model_converter.py
obj_to_vmf_brushes.py
obj_to_vmf_triangles.py
requirements.txt
```

## Launch

```bat
python hammer_model_converter.py
```

## Build in exe

Debugging option:

```bat
python -m pip install pyinstaller
pyinstaller --onedir --noconsole hammer_model_converter.py
```

Option with one exe:

```bat
pyinstaller --onefile --noconsole hammer_model_converter.py
```

After assembly, leave next to the exe:

```text
obj_to_vmf_brushes.py
obj_to_vmf_triangles.py
```

Otherwise, the GUI will not be able to run converters as external scripts.

---------------------

RU:

# hammer model converter

GUI-обёртка для двух Python-конвертеров:

- obj_to_vmf_brushes.py
- obj_to_vmf_triangles.py

## Установка

```bat
python -m pip install -r requirements.txt
```

## Структура папки

Все файлы должны лежать рядом:

```text
hammer_model_converter.py
obj_to_vmf_brushes.py
obj_to_vmf_triangles.py
requirements.txt
```

## Запуск

```bat
python hammer_model_converter.py
```

## Сборка в exe

Вариант для отладки:

```bat
python -m pip install pyinstaller
pyinstaller --onedir --noconsole hammer_model_converter.py
```

Вариант одним exe:

```bat
pyinstaller --onefile --noconsole hammer_model_converter.py
```

После сборки рядом с exe оставь:

```text
obj_to_vmf_brushes.py
obj_to_vmf_triangles.py
```

Иначе GUI не сможет запускать конвертеры как внешние скрипты.
