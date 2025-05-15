# FaceRecognitionService

## 目录结构

```
Service/
  face_recognition_service/
    __init__.py
    service.py
    README.md
    requirements.txt
    known_faces/   # 存放已知人物头像
```

## 使用方法

1. 将已知人物头像按如下方式存放：

```
known_faces/
  ├── Alice/
  │    ├── alice1.jpg
  │    └── alice2.jpg
  └── Bob/
       ├── bob1.jpg
       └── bob2.jpg
```

2. 准备待识别的群体照（如 group.jpg）。

3. 运行 service.py：

```
python service.py
```

4. 识别结果会输出已知人物名单，并在 result.jpg 中标注。 