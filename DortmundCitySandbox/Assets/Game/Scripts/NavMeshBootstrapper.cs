using System.Collections.Generic;
using Unity.AI.Navigation;
using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Builds navmeshes at runtime for streamed city tiles.
    /// </summary>
    public class NavMeshBootstrapper : MonoBehaviour
    {
        [SerializeField] private List<NavMeshSurface> surfaces = new();
        [SerializeField] private bool buildOnStart = true;

        private void Start()
        {
            if (buildOnStart)
            {
                BuildAll();
            }
        }

        public void BuildAll()
        {
            foreach (var surface in surfaces)
            {
                if (surface == null)
                {
                    continue;
                }

                surface.RemoveData();
                surface.BuildNavMesh();
            }
        }
    }
}
