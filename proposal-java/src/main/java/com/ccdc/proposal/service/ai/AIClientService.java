package com.ccdc.proposal.service.ai;

import com.ccdc.proposal.dto.request.ChatRequest;
import com.ccdc.proposal.dto.response.ChatResponse;
import com.ccdc.proposal.dto.response.CheckResponse;
import com.ccdc.proposal.exception.AIClientException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;

@Service
@Slf4j
public class AIClientService {

    private final WebClient webClient;
    private final ObjectMapper objectMapper;

    public AIClientService(WebClient aiWebClient, ObjectMapper objectMapper) {
        this.webClient = aiWebClient;
        this.objectMapper = objectMapper;
    }

    public Mono<Map> generateTeamResponsibilities(Map<String, Object> request) {
        log.info("调用Python生成团队职责");
        return callAIService("/ai/generate/team-responsibilities", request)
                .timeout(Duration.ofSeconds(15))
                .doOnError(e -> log.error("AI生成团队职责失败", e));
    }

    public Mono<Map> generateControlPlan(Map<String, Object> request) {
        log.info("调用Python生成管控方案");
        return callAIService("/ai/generate/control-plan", request)
                .timeout(Duration.ofSeconds(15));
    }

    public Mono<Map> generateSchedule(Map<String, Object> request) {
        log.info("调用Python生成进度计划");
        return callAIService("/ai/generate/schedule", request)
                .timeout(Duration.ofSeconds(15));
    }

    public Mono<Map> generateResourcePlan(Map<String, Object> request) {
        log.info("调用Python生成资源计划");
        return callAIService("/ai/generate/resource-plan", request)
                .timeout(Duration.ofSeconds(15));
    }

    public Mono<Map> generateQualityPlan(Map<String, Object> request) {
        log.info("调用Python生成质量计划");
        return callAIService("/ai/generate/quality-plan", request)
                .timeout(Duration.ofSeconds(15));
    }

    public Mono<ChatResponse> chat(ChatRequest request) {
        log.info("调用Python进行AI对话");
        return callPost("/ai/chat", request, ChatResponse.class)
                .timeout(Duration.ofSeconds(15));
    }

    public Mono<CheckResponse> checkProposal(Map<String, Object> request) {
        log.info("调用Python检查方案书");
        return callPost("/ai/check", request, CheckResponse.class)
                .timeout(Duration.ofSeconds(15));
    }

    private Mono<Map> callAIService(String path, Object request) {
        return callPost(path, request, Map.class);
    }

    private <T> Mono<T> callPost(String path, Object request, Class<T> responseType) {
        log.debug("发送AI请求到 {}", path);
        return webClient.post()
                .uri(path)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .onStatus(
                    status -> status.is4xxClientError(),
                    response -> response.bodyToMono(String.class)
                            .map(errorBody -> new AIClientException("AI服务请求错误: " + errorBody))
                )
                .onStatus(
                    status -> status.is5xxServerError(),
                    response -> Mono.error(new AIClientException("AI服务内部错误，请稍后重试"))
                )
                .bodyToMono(responseType)
                .onErrorMap(e -> !(e instanceof AIClientException),
                        e -> new AIClientException("AI请求失败: " + e.getMessage()));
    }
}
