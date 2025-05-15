import os
import numpy as np
from PIL import Image, ImageDraw
import face_recognition

class FaceRecognitionService:
    def __init__(self, known_dir="known_faces"): 
        self.known_dir = known_dir
        self.known_encodings = []
        self.known_names = []
        self._load_known_faces()

    def _load_known_faces(self):
        """
        加载已知人脸图片并提取特征
        """
        if not os.path.exists(self.known_dir):
            print(f"已知人脸文件夹 {self.known_dir} 不存在！")
            return
        for person in os.listdir(self.known_dir):
            person_dir = os.path.join(self.known_dir, person)
            if not os.path.isdir(person_dir):
                continue
            for img_name in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_name)
                img = face_recognition.load_image_file(img_path)
                encs = face_recognition.face_encodings(img)
                if encs:
                    self.known_encodings.append(encs[0])
                    self.known_names.append(person)

    def recognize_in_image(self, image_path, result_path="result.jpg", threshold=0.4):
        """
        在指定图片中识别人脸并标注
        """
        test_image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(test_image)
        face_encodings = face_recognition.face_encodings(test_image, face_locations)
        pil_img = Image.fromarray(test_image)
        draw = ImageDraw.Draw(pil_img)
        matches = set()
        for (top, right, bottom, left), face_enc in zip(face_locations, face_encodings):
            distances = face_recognition.face_distance(self.known_encodings, face_enc)
            if len(distances) == 0:
                name = "Unknown"
            else:
                best_idx = np.argmin(distances)
                if distances[best_idx] < threshold:
                    name = self.known_names[best_idx]
                    matches.add(name)
                else:
                    name = "Unknown"
            draw.rectangle(((left, top), (right, bottom)), outline=(0, 255, 0), width=2)
            draw.text((left, bottom + 5), name, fill=(0, 255, 0))
        pil_img.save(result_path)
        print(f"识别完成，已标注的照片保存在 {result_path}")
        return list(matches)

if __name__ == "__main__":
    service = FaceRecognitionService(known_dir="known_faces")
    result = service.recognize_in_image("group.jpg", result_path="result.jpg")
    print("照片中出现的已知人物：", result) 