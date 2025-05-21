import pandas as pd
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import accuracy_score, f1_score, classification_report
from gemini_sentiment import batch_sentiment_analysis

# ===================== 데이터 불러오기 =====================
def load_test_data(file_path):
    df = pd.read_excel(file_path)
    df = df[['Sentence', 'Emotion']].dropna()
    texts = df['Sentence'].astype(str).tolist()
    labels = df['Emotion'].astype(int).tolist()
    return texts, labels

# ===================== 중립 제거 (이진 분류용) =====================
def binary_filter(texts, labels):
    filtered_texts, filtered_labels = [], []
    for text, label in zip(texts, labels):
        if label != 0:  # 중립 제거
            filtered_texts.append(text)
            filtered_labels.append(label)
    return filtered_texts, filtered_labels

# ===================== 단일 평가 함수 =====================
def evaluate_sentiment_model(file_path, batch_size=5, max_workers=5, sample_fraction=0.1):
    texts, true_labels = load_test_data(file_path)
    texts, true_labels = binary_filter(texts, true_labels)
    total = len(texts)
    print(f"총 {total}개의 긍정/부정 테스트 샘플을 로드했습니다.")

    sample_size = int(total * sample_fraction)
    texts = texts[:sample_size]
    true_labels = true_labels[:sample_size]
    print(f"{int(sample_fraction*100)}% 샘플 ({sample_size}개)로 평가합니다.")

    predicted_labels = batch_sentiment_analysis(texts, batch_size=batch_size, max_workers=max_workers)

    # 중립(None) 예측 제거
    filtered_preds, filtered_labels = [], []
    for pred, label in zip(predicted_labels, true_labels):
        if pred is not None:
            filtered_preds.append(pred)
            filtered_labels.append(label)

    acc = accuracy_score(filtered_labels, filtered_preds)
    f1 = f1_score(filtered_labels, filtered_preds, average='weighted')
    print(f"\n🔍 전체 정확도: {acc * 100:.2f}%")
    print(f"🔍 전체 F1 Score (가중 평균): {f1:.2f}\n")

    print("🔎 긍정/부정 클래스별 평가:")
    print(classification_report(filtered_labels, filtered_preds, digits=3))

    return filtered_preds, filtered_labels

# ===================== K-Fold 교차검증 평가 =====================
def evaluate_cross_validation(texts, labels, n_splits=5, batch_size=5, max_workers=5):
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    acc_list = []
    f1_list = []

    fold = 1
    for train_idx, test_idx in kf.split(texts):
        print(f"\n📁 Fold {fold} 평가 중...")
        X_test = [texts[i] for i in test_idx]
        y_test = [labels[i] for i in test_idx]

        y_pred = batch_sentiment_analysis(X_test, batch_size=batch_size, max_workers=max_workers)

        # 중립 제거
        filtered_preds, filtered_labels = [], []
        for pred, label in zip(y_pred, y_test):
            if pred is not None:
                filtered_preds.append(pred)
                filtered_labels.append(label)

        acc = accuracy_score(filtered_labels, filtered_preds)
        f1 = f1_score(filtered_labels, filtered_preds, average='weighted')

        print(f"  정확도: {acc * 100:.2f}%")
        print(f"  F1 Score: {f1:.2f}")
        acc_list.append(acc)
        f1_list.append(f1)

        fold += 1

    print("\n✅ 교차검증 평균 결과:")
    print(f"🔹 평균 정확도: {np.mean(acc_list) * 100:.2f}%")
    print(f"🔹 평균 F1 Score: {np.mean(f1_list):.2f}")

# ===================== 실행 예시 =====================
if __name__ == "__main__":
    test_file_path = r"C:\Users\dnjsr\Desktop\진짜 졸작\test_dataset\test_data.xlsx"
    batch_size = 5
    max_workers = 5

    mode = "single"  # "single" 또는 "cross_validation"

    if mode == "single":
        evaluate_sentiment_model(
            test_file_path,
            batch_size=batch_size,
            max_workers=max_workers,
            sample_fraction=1.0
        )
    elif mode == "cross_validation":
        texts, labels = load_test_data(test_file_path)
        texts, labels = binary_filter(texts, labels)
        print(f"총 {len(texts)}개의 긍정/부정 샘플 로드됨. 5-Fold 교차검증 시작.")
        evaluate_cross_validation(
            texts, labels,
            n_splits=5,
            batch_size=batch_size,
            max_workers=max_workers
        )
