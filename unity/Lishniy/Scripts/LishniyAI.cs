using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;

namespace Lishniy
{
    /// <summary>
    /// «Лишний» — тот, кого всегда на одного больше.
    ///
    /// Он никогда не ходит, пока ты смотришь прямо на него.
    /// 1. Эхо: твои шаги звучат дважды. Когда ты останавливаешься — звучит ещё один, лишний.
    /// 2. Пока ты не видишь его — он переставляется ближе, обычно туда, куда ты сейчас обернёшься.
    /// 3. Краем глаза видно, как он медленно идёт к тебе. Посмотришь прямо — замирает,
    ///    а голова медленно поворачивается к тебе, даже если тело стоит спиной.
    /// 4. Когда он прямо за спиной, слышно дыхание. Спастись можно, только если
    ///    НЕ оборачиваться и НЕ останавливаться. Обернулся или встал — конец.
    /// </summary>
    [RequireComponent(typeof(LishniyBody))]
    public class LishniyAI : MonoBehaviour
    {
        public enum State { Stalking, Behind, Caught }

        [Header("Игрок")]
        [Tooltip("Камера игрока. Если пусто — Camera.main.")]
        public Camera playerCamera;
        [Tooltip("Слои, которые закрывают обзор и служат полом.")]
        public LayerMask obstacleMask = Physics.DefaultRaycastLayers;

        [Header("Подкрадывание")]
        public float startDistance = 22f;
        public float approachStep = 3f;
        public Vector2 relocateInterval = new Vector2(3f, 7f);
        [Tooltip("Скорость, с которой он идёт, пока виден только краем глаза.")]
        public float peripheralSpeed = 0.7f;
        [Tooltip("Насколько близко к центру экрана считается «смотрю прямо» (0..0.5).")]
        [Range(0.05f, 0.4f)] public float directLookRadius = 0.17f;
        [Tooltip("Сколько секунд можно смотреть на него, прежде чем свет мигнёт и он исчезнет.")]
        public float maxGazeTime = 2.5f;
        [Tooltip("Градусы в секунду. Медленно — значит страшно.")]
        public float headTurnSpeed = 25f;

        [Header("За спиной")]
        public float behindDistance = 1.1f;
        [Tooltip("Сколько секунд нужно идти не оборачиваясь, чтобы он отстал.")]
        public float surviveTime = 8f;
        [Tooltip("Сколько секунд можно стоять, когда он за спиной.")]
        public float stopGrace = 0.7f;
        public float moveSpeedThreshold = 0.6f;

        [Header("Шаги-эхо")]
        public float strideLength = 1.4f;
        public float echoDelay = 0.33f;
        [Range(0f, 1f)] public float extraStepChance = 0.6f;

        [Header("Свет")]
        public float flickerRadius = 10f;

        [Header("Поимка")]
        public bool reloadSceneOnCatch = true;
        public UnityEvent onCaught;

        [Header("Звуки (пусто — сгенерируются сами)")]
        public AudioClip footstepClip;
        public AudioClip droneClip;
        public AudioClip breathClip;
        public AudioClip stingClip;

        public State CurrentState => state;

        static readonly float[] SamplePoints = { 0.15f, 0.5f, 0.93f };

        LishniyBody body;
        Camera cam;
        State state = State.Stalking;
        AudioSource stepSource, breathSource, droneSource, stingSource;
        Light[] sceneLights;

        float stalkDistance;
        float relocateTimer, nextRelocate;
        float gazeTimer;
        float behindTimer, stopTimer;
        bool busy;
        float overlayAlpha;

        Vector3 lastFeet;
        float playerSpeed, strideAccum, stillTimer;
        bool wasMoving;

        void Awake()
        {
            body = GetComponent<LishniyBody>();
            body.Build();

            if (footstepClip == null) footstepClip = LishniyAudio.Footstep();
            if (droneClip == null) droneClip = LishniyAudio.Drone();
            if (breathClip == null) breathClip = LishniyAudio.Breath();
            if (stingClip == null) stingClip = LishniyAudio.Sting();

            stepSource = MakeSource(true, false, 1f);
            breathSource = MakeSource(true, true, 0.9f);
            breathSource.clip = breathClip;
            droneSource = MakeSource(false, true, 0f);
            droneSource.clip = droneClip;
            stingSource = MakeSource(false, false, 1f);
        }

        void Start()
        {
            cam = playerCamera != null ? playerCamera : Camera.main;
            if (cam == null)
            {
                Debug.LogWarning("Лишний: не найдена камера игрока. Укажите Player Camera.", this);
                enabled = false;
                return;
            }

            sceneLights = FindObjectsByType<Light>(FindObjectsSortMode.None);
            stalkDistance = startDistance;
            nextRelocate = Random.Range(relocateInterval.x, relocateInterval.y);
            lastFeet = PlayerFeet();
            droneSource.Play();
            Relocate(stalkDistance);
        }

        void Update()
        {
            if (state == State.Caught || cam == null) return;
            float dt = Time.deltaTime;

            TrackPlayerMotion(dt);
            UpdateDrone(dt);

            if (busy) return;
            if (state == State.Stalking) UpdateStalking(dt);
            else if (state == State.Behind) UpdateBehind(dt);
        }

        // ---------------- Подкрадывание ----------------

        void UpdateStalking(float dt)
        {
            Vector3 feet = PlayerFeet();
            bool visible = IsVisible(transform.position, out float centerDist);

            if (visible)
            {
                relocateTimer = 0f;
                if (centerDist < directLookRadius)
                {
                    // Смотрят прямо: стоит, голова медленно поворачивается к тебе
                    gazeTimer += dt;
                    TurnHeadToward(cam.transform.position, headTurnSpeed * dt);
                    if (gazeTimer > maxGazeTime)
                        StartCoroutine(VanishAndRelocate(stalkDistance + 4f));
                }
                else
                {
                    // Краем глаза: идёт к тебе
                    gazeTimer = Mathf.Max(0f, gazeTimer - dt);
                    Vector3 to = feet - transform.position;
                    to.y = 0f;
                    if (to.magnitude > behindDistance + 1.5f)
                    {
                        Vector3 next = transform.position + to.normalized * (peripheralSpeed * dt);
                        if (SpaceFree(next)) transform.position = next;
                    }
                    stalkDistance = Mathf.Min(stalkDistance, FlatDistance(transform.position, feet));
                }
                return;
            }

            gazeTimer = 0f;
            relocateTimer += dt;
            if (relocateTimer < nextRelocate) return;

            relocateTimer = 0f;
            nextRelocate = Random.Range(relocateInterval.x, relocateInterval.y);
            stalkDistance = Mathf.Max(behindDistance, stalkDistance - approachStep);

            if (stalkDistance <= behindDistance + 2f) EnterBehind();
            else Relocate(stalkDistance);
        }

        void Relocate(float dist)
        {
            if (!FindSpot(dist, out Vector3 spot) && !FindSpot(dist * 0.6f, out spot)) return;

            transform.position = spot;
            Vector3 toPlayer = PlayerFeet() - spot;
            toPlayer.y = 0f;
            if (toPlayer.sqrMagnitude < 0.01f) toPlayer = Vector3.forward;
            // Половину времени стоит спиной к тебе
            Vector3 facing = Random.value < 0.5f ? toPlayer : -toPlayer;
            transform.rotation = Quaternion.LookRotation(facing.normalized, Vector3.up);
            body.ResetHead();
        }

        bool FindSpot(float dist, out Vector3 result)
        {
            Vector3 feet = PlayerFeet();
            float yaw = cam.transform.eulerAngles.y;

            for (int i = 0; i < 40; i++)
            {
                // Чаще всего — сзади и сбоку: там, куда ты обернёшься
                float angle = i < 28 ? Random.Range(100f, 260f) : Random.Range(0f, 360f);
                float d = dist * Random.Range(0.85f, 1.15f);
                Vector3 dir = Quaternion.Euler(0f, yaw + angle, 0f) * Vector3.forward;
                Vector3 from = feet + dir * d + Vector3.up * 2.5f;

                if (!Physics.Raycast(from, Vector3.down, out RaycastHit hit, 6f, obstacleMask, QueryTriggerInteraction.Ignore))
                    continue;
                if (Mathf.Abs(hit.point.y - feet.y) > 2f) continue;
                if (!SpaceFree(hit.point)) continue;
                if (IsVisible(hit.point, out _)) continue;

                result = hit.point;
                return true;
            }

            result = default;
            return false;
        }

        // ---------------- За спиной ----------------

        void EnterBehind()
        {
            state = State.Behind;
            behindTimer = 0f;
            stopTimer = 0f;
            transform.position = BehindPoint();
            body.SetFaceVisible(true);
            breathSource.Play();
            StartCoroutine(FlickerLights(0.4f));
        }

        void UpdateBehind(float dt)
        {
            Vector3 fwd = FlatForward();
            transform.position = Vector3.Lerp(transform.position, BehindPoint(), 1f - Mathf.Exp(-8f * dt));
            transform.rotation = Quaternion.LookRotation(fwd, Vector3.up);
            TurnHeadToward(cam.transform.position, 360f);

            // Обернулся — поймал
            if (IsVisible(transform.position, out _))
            {
                Catch();
                return;
            }

            // Остановился — поймал
            if (playerSpeed < moveSpeedThreshold)
            {
                stopTimer += dt;
                if (stopTimer > stopGrace)
                {
                    Catch();
                    return;
                }
            }
            else stopTimer = 0f;

            behindTimer += dt;
            if (behindTimer >= surviveTime) StartCoroutine(Retreat());
        }

        Vector3 BehindPoint() => PlayerFeet() - FlatForward() * behindDistance;

        IEnumerator Retreat()
        {
            busy = true;
            breathSource.Stop();
            StartCoroutine(FlickerLights(0.5f));
            yield return StartCoroutine(Blackout(0.12f, () =>
            {
                state = State.Stalking;
                body.SetFaceVisible(false);
                stalkDistance = startDistance;
                Relocate(stalkDistance);
            }));
            nextRelocate = relocateInterval.y + 4f; // даёт передохнуть
            relocateTimer = 0f;
            busy = false;
        }

        IEnumerator VanishAndRelocate(float dist)
        {
            busy = true;
            gazeTimer = 0f;
            StartCoroutine(FlickerLights(0.6f));
            yield return new WaitForSeconds(0.35f);
            yield return StartCoroutine(Blackout(0.1f, () =>
            {
                stalkDistance = Mathf.Min(dist, startDistance);
                Relocate(stalkDistance);
            }));
            busy = false;
        }

        // ---------------- Поимка ----------------

        void Catch()
        {
            if (state == State.Caught) return;
            state = State.Caught;
            StartCoroutine(CatchRoutine());
        }

        IEnumerator CatchRoutine()
        {
            breathSource.Stop();
            body.SetFaceVisible(true);

            Vector3 fwd = FlatForward();
            Vector3 camPos = cam.transform.position;
            transform.position = camPos + fwd * 0.6f - Vector3.up * body.HeadCenterHeight;
            transform.rotation = Quaternion.LookRotation(-fwd, Vector3.up);
            body.Head.LookAt(camPos);
            stingSource.PlayOneShot(stingClip);
            droneSource.volume = 1f;

            // Голова мелко дёргается — будто не умеет держать человеческое лицо
            float t = 0f;
            while (t < 0.9f)
            {
                body.Head.LookAt(camPos);
                body.Head.Rotate(Random.Range(-6f, 6f), Random.Range(-6f, 6f), Random.Range(-25f, 25f), Space.Self);
                t += Time.deltaTime;
                yield return null;
            }

            for (float a = 0f; a < 1f; a += Time.deltaTime / 0.4f)
            {
                overlayAlpha = a;
                yield return null;
            }
            overlayAlpha = 1f;
            droneSource.Stop();
            onCaught?.Invoke();

            if (!reloadSceneOnCatch) yield break;
            yield return new WaitForSeconds(2.5f);
            int index = SceneManager.GetActiveScene().buildIndex;
            if (index >= 0) SceneManager.LoadScene(index);
            else Debug.Log("Лишний: добавьте сцену в Build Profiles, чтобы она перезапускалась после поимки.");
        }

        // ---------------- Звук ----------------

        void TrackPlayerMotion(float dt)
        {
            Vector3 feet = PlayerFeet();
            Vector3 delta = feet - lastFeet;
            delta.y = 0f;
            lastFeet = feet;

            float speed = delta.magnitude / Mathf.Max(dt, 0.0001f);
            playerSpeed = Mathf.Lerp(playerSpeed, speed, 1f - Mathf.Exp(-10f * dt));
            if (speed > 20f) return; // телепорт игрока — не шаги

            strideAccum += delta.magnitude;
            if (strideAccum >= strideLength)
            {
                strideAccum = 0f;
                StartCoroutine(StepLater(echoDelay));
            }

            if (playerSpeed > moveSpeedThreshold)
            {
                wasMoving = true;
                stillTimer = 0f;
            }
            else
            {
                stillTimer += dt;
                // Ты остановился. А он — сделал ещё один шаг.
                if (wasMoving && stillTimer > 0.15f)
                {
                    wasMoving = false;
                    if (Random.value < extraStepChance) StartCoroutine(StepLater(echoDelay + 0.45f));
                }
            }
        }

        IEnumerator StepLater(float delay)
        {
            yield return new WaitForSeconds(delay);
            if (state == State.Caught) yield break;
            stepSource.pitch = Random.Range(0.85f, 1f);
            stepSource.PlayOneShot(footstepClip, Random.Range(0.7f, 1f));
        }

        void UpdateDrone(float dt)
        {
            float dist = FlatDistance(transform.position, PlayerFeet());
            float target = state == State.Behind
                ? 0.9f
                : Mathf.Lerp(0.6f, 0.05f, Mathf.InverseLerp(2f, startDistance, dist)) + gazeTimer * 0.1f;
            droneSource.volume = Mathf.Lerp(droneSource.volume, Mathf.Clamp01(target), 1f - Mathf.Exp(-2f * dt));
        }

        AudioSource MakeSource(bool spatial, bool loop, float volume)
        {
            var src = gameObject.AddComponent<AudioSource>();
            src.playOnAwake = false;
            src.loop = loop;
            src.volume = volume;
            src.spatialBlend = spatial ? 1f : 0f;
            src.rolloffMode = AudioRolloffMode.Linear;
            src.minDistance = 1f;
            src.maxDistance = 35f;
            return src;
        }

        // ---------------- Свет и затемнение ----------------

        IEnumerator FlickerLights(float duration)
        {
            var list = new List<(Light light, float intensity)>();
            Vector3 a = transform.position, b = cam.transform.position;
            foreach (Light l in sceneLights)
            {
                if (l == null || !l.enabled || l.type == LightType.Directional) continue;
                Vector3 p = l.transform.position;
                if (Vector3.Distance(p, a) < flickerRadius || Vector3.Distance(p, b) < flickerRadius)
                    list.Add((l, l.intensity));
            }

            float t = 0f;
            while (t < duration)
            {
                foreach (var e in list)
                    if (e.light != null)
                        e.light.intensity = Random.value < 0.45f ? 0f : e.intensity * Random.Range(0.3f, 1.1f);
                float step = Random.Range(0.03f, 0.09f);
                t += step;
                yield return new WaitForSeconds(step);
            }

            foreach (var e in list)
                if (e.light != null) e.light.intensity = e.intensity;
        }

        IEnumerator Blackout(float duration, System.Action duringDark)
        {
            overlayAlpha = 1f;
            duringDark?.Invoke();
            yield return new WaitForSeconds(duration);
            overlayAlpha = 0f;
        }

        void OnGUI()
        {
            if (overlayAlpha <= 0.001f) return;
            Color old = GUI.color;
            GUI.color = new Color(0f, 0f, 0f, overlayAlpha);
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = old;
        }

        // ---------------- Геометрия ----------------

        bool IsVisible(Vector3 basePos, out float centerDist)
        {
            centerDist = 99f;
            bool any = false;
            Vector3 eye = cam.transform.position;

            foreach (float h in SamplePoints)
            {
                Vector3 pt = basePos + Vector3.up * (body.Height * h);
                Vector3 vp = cam.WorldToViewportPoint(pt);
                if (vp.z <= 0.05f || vp.x < -0.02f || vp.x > 1.02f || vp.y < -0.02f || vp.y > 1.02f) continue;

                Vector3 dir = pt - eye;
                float len = dir.magnitude;
                if (Physics.Raycast(eye, dir / len, len - 0.2f, obstacleMask, QueryTriggerInteraction.Ignore)) continue;

                any = true;
                centerDist = Mathf.Min(centerDist, Vector2.Distance(new Vector2(vp.x, vp.y), new Vector2(0.5f, 0.5f)));
            }
            return any;
        }

        bool SpaceFree(Vector3 feet)
        {
            const float r = 0.3f;
            return !Physics.CheckCapsule(feet + Vector3.up * (r + 0.05f), feet + Vector3.up * (body.Height - r), r,
                obstacleMask, QueryTriggerInteraction.Ignore);
        }

        Vector3 PlayerFeet()
        {
            Vector3 c = cam.transform.position;
            if (Physics.Raycast(c, Vector3.down, out RaycastHit hit, 4f, obstacleMask, QueryTriggerInteraction.Ignore))
                return hit.point;
            return c + Vector3.down * 1.7f;
        }

        Vector3 FlatForward()
        {
            Vector3 f = cam.transform.forward;
            f.y = 0f;
            return f.sqrMagnitude < 0.001f ? transform.forward : f.normalized;
        }

        void TurnHeadToward(Vector3 target, float maxDegrees)
        {
            Transform head = body.Head;
            Vector3 dir = target - head.position;
            if (dir.sqrMagnitude < 0.0001f) return;
            head.rotation = Quaternion.RotateTowards(head.rotation, Quaternion.LookRotation(dir, Vector3.up), maxDegrees);
        }

        static float FlatDistance(Vector3 a, Vector3 b)
        {
            a.y = 0f;
            b.y = 0f;
            return Vector3.Distance(a, b);
        }
    }
}
