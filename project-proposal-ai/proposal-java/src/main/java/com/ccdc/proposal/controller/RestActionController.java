package com.ccdc.proposal.controller;

import com.ccdc.proposal.entity.Project;
import com.ccdc.proposal.exception.BusinessException;
import com.ccdc.proposal.service.ProjectService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/portal")
@Slf4j
public class RestActionController {

    @Resource
    private ProjectService projectService;

    @Resource
    private ObjectMapper objectMapper;

    @PostMapping("/RestAction.invoke.do")
    public ResponseEntity<?> invoke(@RequestParam String url,
                                     @RequestParam(required = false) String param) {
        try {
            Map<String, Object> params = parseParam(param);
            Object result = route(url, params);
            return ResponseEntity.ok(result);
        } catch (BusinessException e) {
            log.warn("业务异常 [{}]: {}", url, e.getMessage());
            Map<String, Object> error = new HashMap<>();
            error.put("code", "BUSINESS_ERROR");
            error.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(error);
        } catch (Exception e) {
            log.error("系统异常 [{}]", url, e);
            Map<String, Object> error = new HashMap<>();
            error.put("code", "SYSTEM_ERROR");
            error.put("message", "系统繁忙，请稍后重试");
            return ResponseEntity.status(500).body(error);
        }
    }

    private Map<String, Object> parseParam(String param) {
        if (param == null || param.isBlank()) {
            return new HashMap<>();
        }
        try {
            return objectMapper.readValue(param, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            log.warn("参数解析失败: {}", param);
            throw new BusinessException("参数格式错误，无法解析JSON");
        }
    }

    @SuppressWarnings("unchecked")
    private Object route(String url, Map<String, Object> params) {
        switch (url) {
            case "/itmp/pmProjectService/findProjectById" -> {
                String id = getString(params, "id");
                if (id == null || id.isBlank()) {
                    throw new BusinessException("id不能为空");
                }
                return projectService.findProjectById(id);
            }
            case "/itmp/pmProjectService/updatePmProject" -> {
                if (params.isEmpty()) {
                    throw new BusinessException("param参数不能为空");
                }
                return projectService.updatePmProject(params);
            }
            case "/itmp/pmProjectMemberService/findPmProjectMemberList" -> {
                String pmProjectId = getString(params, "pmProjectId");
                if (pmProjectId == null || pmProjectId.isBlank()) {
                    throw new BusinessException("pmProjectId不能为空");
                }
                String nickname = getString(params, "nickname");
                List<String> roleIds = getStringList(params, "roleIds");
                Map<String, Object> pageable = (Map<String, Object>) params.get("pageable");
                int page = 0;
                int size = 10;
                if (pageable != null) {
                    Object p = pageable.get("page");
                    Object s = pageable.get("size");
                    if (p instanceof Number) page = ((Number) p).intValue();
                    else if (p != null) page = Integer.parseInt(p.toString());
                    if (s instanceof Number) size = ((Number) s).intValue();
                    else if (s != null) size = Integer.parseInt(s.toString());
                }
                if (size < 1) size = 10;
                if (page < 0) page = 0;
                return projectService.findPmProjectMemberList(pmProjectId, nickname, roleIds, page, size);
            }
            case "/itmp/pmProjectMemberService/createPmProjectMembers" -> {
                String pmProjectId = getString(params, "pmProjectId");
                List<String> userIds = getStringList(params, "userIds");
                if (pmProjectId == null || pmProjectId.isBlank()) {
                    throw new BusinessException("pmProjectId不能为空");
                }
                return projectService.createPmProjectMembers(pmProjectId, userIds);
            }
            case "/itmp/pmProjectMemberService/deletePmProjectMembers" -> {
                String pmProjectId = getString(params, "pmProjectId");
                List<String> userIds = getStringList(params, "userIds");
                List<String> ids = getStringList(params, "ids");
                if (pmProjectId == null || pmProjectId.isBlank()) {
                    throw new BusinessException("pmProjectId不能为空");
                }
                return projectService.deletePmProjectMembers(pmProjectId, userIds, ids);
            }
            case "/itmp/pmProjectMemberService/updateMemberRoles" -> {
                String id = getString(params, "id");
                String userId = getString(params, "userId");
                String projectId = getString(params, "projectId");
                List<String> roleIds = getStringList(params, "roleIds");
                if ((id == null || id.isBlank()) && (userId == null || userId.isBlank())) {
                    throw new BusinessException("id 或 userId 至少提供一个");
                }
                return projectService.updateMemberRoles(id, userId, projectId, roleIds);
            }
            case "/portal/abikoleManagerService/updateDuty" -> {
                String rid = getString(params, "rid");
                List<String> ids = getStringList(params, "ids");
                String pid = getString(params, "pid");
                boolean checked = getBoolean(params, "checked", true);
                return projectService.updateDuty(rid, ids, pid, checked);
            }
            case "/itmp/pmProjectmanagement/findUserById" -> {
                String id = getString(params, "id");
                if (id == null || id.isBlank()) {
                    throw new BusinessException("id不能为空");
                }
                return projectService.findUserById(id);
            }
            case "/itmp/pmProjectPlanService/findProjectProgramPlanTreeByProjectId" -> {
                String projectId = getString(params, "projectId");
                if (projectId == null || projectId.isBlank()) {
                    throw new BusinessException("projectId不能为空");
                }
                return projectService.findProjectProgramPlanTreeByProjectId(projectId);
            }
            case "/itmp/pmProjectPlanService/savePlanTaskCutResult" -> {
                List<Map<String, Object>> tasks = (List<Map<String, Object>>) params.get("tasks");
                return projectService.savePlanTaskCutResult(tasks);
            }
            case "/itmp/pmProjectPlanService/findAssetByProjectProgramPage" -> {
                String rel = getString(params, "rel");
                String projectId = getString(params, "projectId");
                if (projectId == null || projectId.isBlank()) {
                    throw new BusinessException("projectId不能为空");
                }
                return projectService.findAssetByProjectProgramPage(rel, projectId);
            }
            case "/itmp/pmProjectPlanService/savePlanTaskRel" -> {
                List<Map<String, Object>> rel = (List<Map<String, Object>>) params.get("rel");
                return projectService.savePlanTaskRel(rel);
            }
            case "/itmp/pmProjectmanagement/findRelProject" -> {
                String rel = getString(params, "rel");
                String projectId = getString(params, "projectId");
                if (projectId == null || projectId.isBlank()) {
                    throw new BusinessException("projectId不能为空");
                }
                return projectService.findRelProject(rel, projectId);
            }
            default -> throw new BusinessException("不支持的接口路径: " + url);
        }
    }

    private boolean getBoolean(Map<String, Object> params, String key, boolean defaultValue) {
        Object value = params.get(key);
        if (value == null) return defaultValue;
        if (value instanceof Boolean) return (Boolean) value;
        return Boolean.parseBoolean(value.toString());
    }

    private String getString(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (value == null) return null;
        return value.toString();
    }

    @SuppressWarnings("unchecked")
    private List<String> getStringList(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (value == null) return null;
        if (value instanceof List) {
            List<?> list = (List<?>) value;
            List<String> result = new ArrayList<>();
            for (Object item : list) {
                if (item != null) {
                    result.add(item.toString());
                }
            }
            return result;
        }
        return null;
    }
}
