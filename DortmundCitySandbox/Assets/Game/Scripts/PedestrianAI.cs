using UnityEngine;
using UnityEngine.AI;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Lightweight pedestrian brain that wanders between navmesh targets.
    /// </summary>
    [RequireComponent(typeof(NavMeshAgent))]
    public class PedestrianAI : MonoBehaviour
    {
        [SerializeField] private float idleTime = 4f;
        [SerializeField] private float wanderRadius = 20f;

        private NavMeshAgent agent;
        private float idleTimer;

        private void Awake()
        {
            agent = GetComponent<NavMeshAgent>();
        }

        private void Update()
        {
            if (agent.pathPending || agent.remainingDistance > 0.5f)
            {
                return;
            }

            idleTimer += Time.deltaTime;
            if (idleTimer < idleTime)
            {
                return;
            }

            idleTimer = 0f;
            Vector3 randomDirection = Random.insideUnitSphere * wanderRadius;
            randomDirection += transform.position;
            if (NavMesh.SamplePosition(randomDirection, out var hit, wanderRadius, NavMesh.AllAreas))
            {
                agent.SetDestination(hit.position);
            }
        }
    }
}
