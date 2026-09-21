import os
os.environ.setdefault("MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD", "false")

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

mlflow.set_tracking_uri("http://localhost:5001")
mlflow.set_experiment("hello-mlflow")

# Iris viene incluido en scikit-learn, no hace falta descargar nada
X, y = load_iris(return_X_y=True, as_frame=True)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

hiperparametros = {"C": 1.0, "max_iter": 200, "solver": "lbfgs"}

with mlflow.start_run(run_name="regresion-logistica-iris"):
    modelo = LogisticRegression(**hiperparametros)
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    metricas = {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1_macro": f1_score(y_test, y_pred, average="macro"),
    }

    mlflow.log_params(hiperparametros)
    mlflow.log_metrics(metricas)

    # Artefacto de texto: el reporte por clase
    with open("classification_report.txt", "w") as f:
        f.write(classification_report(y_test, y_pred, target_names=load_iris().target_names))
    mlflow.log_artifact("classification_report.txt")

    # El modelo se guarda en MinIO junto con su firma, listo para servirse
    mlflow.sklearn.log_model(
        sk_model=modelo,
        name="modelo",
        signature=infer_signature(X_train, modelo.predict(X_train)),
        input_example=X_train.head(5),
    )

    print(f"accuracy = {metricas['accuracy']:.4f}")
    print(f"f1_macro = {metricas['f1_macro']:.4f}")
