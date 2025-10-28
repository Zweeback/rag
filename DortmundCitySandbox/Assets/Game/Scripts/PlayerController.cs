using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Basic character controller enabling walking around the Dortmund tile and entering vehicles.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        [Header("Movement")]
        [SerializeField] private float moveSpeed = 5f;
        [SerializeField] private float rotationSpeed = 180f;

        [Header("Jetpack")]
        [SerializeField] private JetpackController jetpack;

        private CharacterController characterController;

        private void Awake()
        {
            characterController = GetComponent<CharacterController>();
        }

        private void Update()
        {
            HandleMovement();
            HandleJetpackToggle();
        }

        private void HandleMovement()
        {
            float horizontal = Input.GetAxis("Horizontal");
            float vertical = Input.GetAxis("Vertical");

            Vector3 direction = new Vector3(horizontal, 0f, vertical);
            if (direction.sqrMagnitude > 0.001f)
            {
                Vector3 worldDirection = transform.TransformDirection(direction.normalized);
                characterController.SimpleMove(worldDirection * moveSpeed);
                Quaternion targetRotation = Quaternion.LookRotation(worldDirection, Vector3.up);
                transform.rotation = Quaternion.RotateTowards(transform.rotation, targetRotation, rotationSpeed * Time.deltaTime);
            }
        }

        private void HandleJetpackToggle()
        {
            if (jetpack == null)
            {
                return;
            }

            if (Input.GetButtonDown("Jump"))
            {
                jetpack.Toggle();
            }
        }
    }
}
