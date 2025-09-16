import os
import random
import shutil
import tensorflow as tf
import matplotlib.pyplot as plt
from tensorflow.keras import layers, models
from sklearn.model_selection import train_test_split

# =============================
# 參數設定
# =============================
ORIGIN_ROOT = r"D:/LiuChiYu/emotionRecognition/Analysis/Data/FinalFullVideos_subjects_facesALL"
TEMP_ROOT = "Analysis/Data/Person2_split_dataset"
IMG_SIZE = (112, 112)
BATCH_SIZE = 32
SEED = 42
EPOCHS = 20
SPLIT_RATIO = (0.7, 0.1, 0.2)  # Train/Val/Test
MODEL_SAVE_NAME = "person2_microexpression_cnn.h5"

# =============================
# 步驟 1：對 Person_2 的圖片進行切分
# =============================
def collect_and_split_data():
    print("🔍 正在搜尋 Person_2 的所有圖片並分割...")
    all_data = []

    for emotion in os.listdir(ORIGIN_ROOT):
        emotion_path = os.path.join(ORIGIN_ROOT, emotion, "Person_2")
        if not os.path.isdir(emotion_path):
            continue
        for root, _, files in os.walk(emotion_path):
            for file in files:
                if file.lower().endswith((".jpg", ".png")):
                    full_path = os.path.join(root, file)
                    all_data.append((full_path, emotion))

    print(f"✅ 總共找到圖片數量：{len(all_data)}")
    random.seed(SEED)
    random.shuffle(all_data)

    train_val, test = train_test_split(all_data, test_size=SPLIT_RATIO[2], random_state=SEED)
    train, val = train_test_split(train_val, test_size=SPLIT_RATIO[1]/(SPLIT_RATIO[0]+SPLIT_RATIO[1]), random_state=SEED)

    dataset_splits = {'train': train, 'val': val, 'test': test}

    if os.path.exists(TEMP_ROOT):
        shutil.rmtree(TEMP_ROOT)

    print("🛠️ 開始複製圖片...")
    for split_name, data_list in dataset_splits.items():
        print(f"🔹 複製 {split_name} 集合，共 {len(data_list)} 張")
        for i, (img_path, label) in enumerate(data_list, start=1):
            dest_dir = os.path.join(TEMP_ROOT, split_name, label)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(img_path, os.path.join(dest_dir, os.path.basename(img_path)))
            if i % 100 == 0 or i == len(data_list):
                print(f"   ➤ 已複製 {i}/{len(data_list)} 張")

    print("✅ Person_2 資料完成切分至:", TEMP_ROOT)


# =============================
# 步驟 2：載入資料集
# =============================
def load_datasets():
    AUTOTUNE = tf.data.AUTOTUNE

    train_ds = tf.keras.preprocessing.image_dataset_from_directory(
        os.path.join(TEMP_ROOT, 'train'),
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        seed=SEED,
        label_mode='int',
        interpolation='bilinear'
    )

    val_ds = tf.keras.preprocessing.image_dataset_from_directory(
        os.path.join(TEMP_ROOT, 'val'),
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        seed=SEED,
        label_mode='int',
        interpolation='bilinear'
    )

    test_ds = tf.keras.preprocessing.image_dataset_from_directory(
        os.path.join(TEMP_ROOT, 'test'),
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        seed=SEED,
        label_mode='int',
        interpolation='bilinear'
    )

    class_names = train_ds.class_names

    train_ds = train_ds.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
    val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)
    test_ds = test_ds.cache().prefetch(buffer_size=AUTOTUNE)

    print("📚 類別:", class_names)
    return train_ds, val_ds, test_ds, class_names


# =============================
# 步驟 3：建立 CNN 模型
# =============================
def create_model(num_classes):
    model = models.Sequential([
        layers.Rescaling(1./255, input_shape=(112, 112, 3)),
        layers.Conv2D(32, 3, activation='relu'),
        layers.MaxPooling2D(),
        layers.Conv2D(64, 3, activation='relu'),
        layers.MaxPooling2D(),
        layers.Conv2D(128, 3, activation='relu'),
        layers.MaxPooling2D(),
        layers.Flatten(),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(num_classes, activation='softmax')
    ])

    model.compile(optimizer='adam',
                  loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])
    model.summary()
    return model


# =============================
# 主程式：整合訓練與評估
# =============================
if __name__ == "__main__":
    collect_and_split_data()
    train_ds, val_ds, test_ds, class_names = load_datasets()
    model = create_model(num_classes=len(class_names))

    print("🚀 開始訓練模型...")
    history = model.fit(train_ds, validation_data=val_ds, epochs=EPOCHS)

    print("🧪 測試集評估...")
    test_loss, test_acc = model.evaluate(test_ds)
    print(f"✅ 測試準確率：{test_acc:.4f}")

    # 儲存模型
    model.save(MODEL_SAVE_NAME)
    print(f"💾 模型已儲存為 {MODEL_SAVE_NAME}")

    # 可選：畫出訓練曲線
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 2, 1)
    plt.plot(history.history['accuracy'], label='Train Acc')
    plt.plot(history.history['val_accuracy'], label='Val Acc')
    plt.title('Accuracy')
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(history.history['loss'], label='Train Loss')
    plt.plot(history.history['val_loss'], label='Val Loss')
    plt.title('Loss')
    plt.legend()
    plt.tight_layout()
    plt.savefig("training_curve.png")
    plt.show()

    # TensorFlow.js 提示
    print("\n💡 若要轉為 TensorFlow.js 可執行：")
    print(f"tensorflowjs_converter --input_format keras {MODEL_SAVE_NAME} tfjs_model/")
