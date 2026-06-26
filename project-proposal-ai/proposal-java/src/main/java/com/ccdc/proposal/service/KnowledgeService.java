package com.ccdc.proposal.service;

import com.ccdc.proposal.entity.KnowledgeRule;
import com.ccdc.proposal.repository.KnowledgeRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@Slf4j
public class KnowledgeService {

    @Resource
    private KnowledgeRepository knowledgeRepository;

    @Resource
    private ObjectMapper objectMapper;

    @Cacheable(value = "knowledgeRules", key = "#projectLevel + '_' + #ruleType")
    public Map<String, Object> getRules(String projectLevel, String ruleType) {
        List<KnowledgeRule> rules = knowledgeRepository
                .findByProjectLevelAndRuleTypeAndIsActiveTrue(projectLevel, ruleType);

        Map<String, Object> result = new HashMap<>();
        for (KnowledgeRule rule : rules) {
            try {
                Map<String, Object> content = objectMapper.readValue(
                        rule.getRuleContent(), new TypeReference<Map<String, Object>>() {});
                result.putAll(content);
            } catch (Exception e) {
                log.warn("解析知识库规则失败: {}", rule.getId(), e);
            }
        }
        return result;
    }

    public List<Map<String, Object>> getAllRules(String projectLevel) {
        List<KnowledgeRule> rules = knowledgeRepository
                .findByProjectLevelAndIsActiveTrue(projectLevel);
        return rules.stream().<Map<String, Object>>map(r -> {
            try {
                return objectMapper.readValue(r.getRuleContent(),
                        new TypeReference<Map<String, Object>>() {});
            } catch (Exception e) {
                return Map.of("error", "解析失败");
            }
        }).collect(Collectors.toList());
    }
}
