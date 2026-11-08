using UnityEditor;
using UnityEngine;

namespace Lishniy.EditorTools
{
    public static class LishniyMenu
    {
        [MenuItem("GameObject/Монстры/Лишний", false, 10)]
        static void Create(MenuCommand command)
        {
            var go = new GameObject("Лишний");
            go.AddComponent<LishniyAI>(); // LishniyBody добавится сам
            go.GetComponent<LishniyBody>().Build();
            GameObjectUtility.SetParentAndAlign(go, command.context as GameObject);
            Undo.RegisterCreatedObjectUndo(go, "Создать Лишнего");
            Selection.activeObject = go;
        }
    }
}
