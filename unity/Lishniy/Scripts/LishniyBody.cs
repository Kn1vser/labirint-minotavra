using UnityEngine;

namespace Lishniy
{
    /// <summary>
    /// Тело «Лишнего», собранное из примитивов — моделей и текстур не нужно.
    /// Слишком высокий, слишком худой, руки ниже колен, длинная шея.
    /// Лицо гладкое; глаза-провалы и вертикальный рот появляются,
    /// только когда он совсем рядом.
    /// </summary>
    public class LishniyBody : MonoBehaviour
    {
        const float DesignHeight = 3.16f; // высота в «чертёжных» единицах ниже
        const float HeadPivotY = 2.8f;
        const float HeadCenterY = 2.97f;

        [Tooltip("Рост в метрах. Чуть выше дверного проёма — так страшнее.")]
        public float height = 2.45f;
        public Color skinColor = new Color(0.80f, 0.78f, 0.74f);

        public Transform Head { get; private set; }
        public float Height => height;
        public float HeadCenterHeight => HeadCenterY * height / DesignHeight;

        GameObject face;

        void Awake() => Build();

        public void Build()
        {
            Transform existing = transform.Find("Model");
            if (existing != null)
            {
                Head = existing.Find("HeadPivot");
                face = Head != null ? Head.Find("Face")?.gameObject : null;
                return;
            }

            Material skin = MakeMaterial(skinColor, 0.15f);
            Material dark = MakeMaterial(new Color(0.02f, 0.015f, 0.015f), 0.85f);

            Transform model = new GameObject("Model").transform;
            model.SetParent(transform, false);
            model.localScale = Vector3.one * (height / DesignHeight);

            // Ноги
            Part(PrimitiveType.Cylinder, model, "LegL", new Vector3(-0.12f, 0.65f, 0f), new Vector3(0.16f, 0.65f, 0.16f), new Vector3(0, 0, -3f), skin);
            Part(PrimitiveType.Cylinder, model, "LegR", new Vector3(0.12f, 0.65f, 0f), new Vector3(0.16f, 0.65f, 0.16f), new Vector3(0, 0, 3f), skin);

            // Туловище — узкое, чуть сутулое
            Part(PrimitiveType.Capsule, model, "Torso", new Vector3(0f, 1.85f, 0.02f), new Vector3(0.40f, 0.6f, 0.22f), new Vector3(8f, 0, 0), skin);
            Part(PrimitiveType.Cube, model, "Shoulders", new Vector3(0f, 2.36f, 0.04f), new Vector3(0.62f, 0.08f, 0.16f), Vector3.zero, skin);

            // Руки — свисают ниже колен
            for (int side = -1; side <= 1; side += 2)
            {
                float x = 0.31f * side;
                Part(PrimitiveType.Cylinder, model, side < 0 ? "ArmL" : "ArmR", new Vector3(x, 1.48f, 0.04f), new Vector3(0.09f, 0.9f, 0.09f), new Vector3(0, 0, 2.5f * side), skin);
                for (int f = 0; f < 4; f++)
                {
                    float fx = x + side * 0.02f + (f - 1.5f) * 0.025f;
                    Part(PrimitiveType.Cylinder, model, "Finger", new Vector3(fx, 0.5f, 0.04f + (f - 1.5f) * 0.012f),
                        new Vector3(0.022f, 0.12f, 0.022f), new Vector3(0, 0, side * (2f + f * 2f)), skin);
                }
            }

            // Шея — слишком длинная
            Part(PrimitiveType.Cylinder, model, "Neck", new Vector3(0f, 2.6f, 0.05f), new Vector3(0.085f, 0.22f, 0.085f), Vector3.zero, skin);

            // Голова на отдельном шарнире: может повернуться на 180°, пока тело стоит спиной
            Head = new GameObject("HeadPivot").transform;
            Head.SetParent(model, false);
            Head.localPosition = new Vector3(0f, HeadPivotY, 0.05f);
            Part(PrimitiveType.Sphere, Head, "Head", new Vector3(0f, HeadCenterY - HeadPivotY, 0f), new Vector3(0.26f, 0.38f, 0.27f), Vector3.zero, skin);

            face = new GameObject("Face");
            face.transform.SetParent(Head, false);
            Part(PrimitiveType.Sphere, face.transform, "EyeL", new Vector3(-0.055f, 0.21f, 0.125f), new Vector3(0.055f, 0.035f, 0.03f), Vector3.zero, dark);
            Part(PrimitiveType.Sphere, face.transform, "EyeR", new Vector3(0.055f, 0.21f, 0.125f), new Vector3(0.055f, 0.035f, 0.03f), Vector3.zero, dark);
            // Рот вертикальный — от этого лицо кажется «неправильным»
            Part(PrimitiveType.Cube, face.transform, "Mouth", new Vector3(0f, 0.07f, 0.11f), new Vector3(0.018f, 0.12f, 0.03f), Vector3.zero, dark);
            face.SetActive(false);

            SetLayerRecursive(transform, 2); // Ignore Raycast — не мешает лучам видимости
        }

        public void SetFaceVisible(bool visible)
        {
            if (face != null) face.SetActive(visible);
        }

        public void ResetHead()
        {
            if (Head != null) Head.localRotation = Quaternion.identity;
        }

        static GameObject Part(PrimitiveType type, Transform parent, string name, Vector3 pos, Vector3 scale, Vector3 euler, Material mat)
        {
            GameObject go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            go.transform.localEulerAngles = euler;
            go.GetComponent<Renderer>().sharedMaterial = mat;

            Collider c = go.GetComponent<Collider>();
            if (Application.isPlaying) Destroy(c);
            else DestroyImmediate(c);
            return go;
        }

        static Material MakeMaterial(Color color, float smoothness)
        {
            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("HDRP/Lit");
            if (shader == null) shader = Shader.Find("Standard");

            var mat = new Material(shader) { color = color };
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", smoothness);
            if (mat.HasProperty("_Glossiness")) mat.SetFloat("_Glossiness", smoothness);
            return mat;
        }

        static void SetLayerRecursive(Transform t, int layer)
        {
            t.gameObject.layer = layer;
            foreach (Transform child in t) SetLayerRecursive(child, layer);
        }
    }
}
