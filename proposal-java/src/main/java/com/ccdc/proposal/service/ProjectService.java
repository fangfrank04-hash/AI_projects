package com.ccdc.proposal.service;

import com.ccdc.proposal.entity.*;
import com.ccdc.proposal.exception.AccessDeniedException;
import com.ccdc.proposal.exception.BusinessException;
import com.ccdc.proposal.repository.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@Slf4j
public class ProjectService {

    @Resource
    private ProjectRepository projectRepository;

    @Resource
    private TeamMemberRepository teamMemberRepository;

    @Resource
    private ProjectProgramPlanRepository planRepository;

    @Resource
    private ProjectDeliverableRepository deliverableRepository;

    @Resource
    private RelatedProjectRepository relatedProjectRepository;

    @Resource
    private ObjectMapper objectMapper;

    // ========== 项目基本信息 ==========

    public Project getProject(String projectId) {
        return projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));
    }

    public Project findProjectById(String id) {
        return getProject(id);
    }

    @Transactional
    public Map<String, Object> updatePmProject(Map<String, Object> projectData) {
        String id = (String) projectData.get("id");
        if (id == null || id.isBlank()) {
            throw new BusinessException("项目ID不能为空");
        }
        Project project = projectRepository.findById(id)
                .orElseThrow(() -> new BusinessException("项目不存在"));

        // v2仅允许修改 productNo 和 productName
        Object productNo = projectData.get("productNo");
        if (productNo != null) {
            project.setProductNo(productNo.toString());
        }
        Object productName = projectData.get("productName");
        if (productName != null) {
            project.setProductName(productName.toString());
        }
        project.setUpdatedAt(LocalDateTime.now());
        projectRepository.save(project);

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "更新成功");
        return result;
    }

    // ========== 项目团队 ==========

    public List<TeamMember> getTeamMembers(String projectId) {
        return teamMemberRepository.findByProjectId(projectId);
    }

    public Map<String, Object> findPmProjectMemberList(String pmProjectId, String nickname,
                                                        List<String> roleIds, int page, int size) {
        List<TeamMember> allMembers = teamMemberRepository.findByProjectId(pmProjectId);

        // 昵称模糊过滤
        if (nickname != null && !nickname.isBlank()) {
            String lower = nickname.toLowerCase();
            allMembers = allMembers.stream()
                    .filter(m -> m.getNickname() != null && m.getNickname().toLowerCase().contains(lower))
                    .collect(Collectors.toList());
        }

        // roleIds 过滤
        if (roleIds != null && !roleIds.isEmpty()) {
            allMembers = allMembers.stream()
                    .filter(m -> m.getRoleIds() != null &&
                            m.getRoleIds().stream().anyMatch(roleIds::contains))
                    .collect(Collectors.toList());
        }

        int total = allMembers.size();
        int start = page * size;
        int end = Math.min(start + size, total);
        List<TeamMember> pageContent = start >= total ? Collections.emptyList() : allMembers.subList(start, end);

        Map<String, Object> result = new HashMap<>();
        result.put("content", pageContent);
        result.put("totalElements", total);
        result.put("totalPages", (int) Math.ceil((double) total / size));
        result.put("number", page);
        result.put("size", size);
        return result;
    }

    @Transactional
    public Map<String, Object> createPmProjectMembers(String pmProjectId, List<String> userIds) {
        if (userIds == null || userIds.isEmpty()) {
            throw new BusinessException("用户ID列表不能为空");
        }
        Project project = projectRepository.findById(pmProjectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));

        for (String userId : userIds) {
            // 检查是否已存在
            List<TeamMember> existing = teamMemberRepository.findByProjectId(pmProjectId);
            boolean alreadyExists = existing.stream()
                    .anyMatch(m -> userId.equals(m.getUserId()));
            if (alreadyExists) {
                continue;
            }
            // 新增成员（仅设置userId，其他信息需后续补充）
            TeamMember member = new TeamMember();
            member.setProject(project);
            member.setUserId(userId);
            member.setName(userId); // 默认用userId作为name
            member.setNickname(userId);
            member.setRole("待分配");
            member.setResponsibilities(Collections.emptyList());
            member.setRoleIds(Collections.emptyList());
            member.setCreatedAt(LocalDateTime.now());
            teamMemberRepository.save(member);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "添加成功");
        return result;
    }

    @Transactional
    public Map<String, Object> deletePmProjectMembers(String pmProjectId, List<String> userIds, List<String> ids) {
        if ((userIds == null || userIds.isEmpty()) && (ids == null || ids.isEmpty())) {
            throw new BusinessException("userIds 和 ids 至少提供一个");
        }

        List<TeamMember> toDelete = new ArrayList<>();
        if (ids != null && !ids.isEmpty()) {
            for (String id : ids) {
                try {
                    Long longId = Long.parseLong(id);
                    teamMemberRepository.findById(longId).ifPresent(toDelete::add);
                } catch (NumberFormatException e) {
                    log.warn("无效的ID格式: {}", id);
                }
            }
        }
        if (userIds != null && !userIds.isEmpty()) {
            List<TeamMember> members = teamMemberRepository.findByProjectId(pmProjectId);
            for (String userId : userIds) {
                members.stream()
                        .filter(m -> userId.equals(m.getUserId()))
                        .forEach(toDelete::add);
            }
        }

        // 去重
        Set<Long> deleteIds = toDelete.stream().map(TeamMember::getId).collect(Collectors.toSet());
        for (Long id : deleteIds) {
            teamMemberRepository.deleteById(id);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "删除成功");
        return result;
    }

    @Transactional
    public Map<String, Object> updateMemberRoles(String id, String userId, String projectId, List<String> roleIds) {
        TeamMember member = null;

        if (id != null && !id.isBlank()) {
            try {
                Long memberId = Long.parseLong(id);
                member = teamMemberRepository.findById(memberId).orElse(null);
            } catch (NumberFormatException e) {
                // id 不是数字，尝试按 userId + projectId 查找
            }
        }

        if (member == null && userId != null && projectId != null) {
            List<TeamMember> members = teamMemberRepository.findByProjectId(projectId);
            member = members.stream()
                    .filter(m -> userId.equals(m.getUserId()))
                    .findFirst()
                    .orElse(null);
        }

        if (member == null) {
            throw new BusinessException("成员不存在");
        }

        if (roleIds != null) {
            member.setRoleIds(roleIds);
        }
        if (userId != null) {
            member.setUserId(userId);
        }
        teamMemberRepository.save(member);

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "角色更新成功");
        return result;
    }

    @Transactional
    public Map<String, Object> updateDuty(String rid, List<String> ids, String pid, boolean checked) {
        if (rid == null || rid.isBlank() || ids == null || ids.isEmpty() || pid == null || pid.isBlank()) {
            throw new BusinessException("rid、ids、pid 均不能为空");
        }

        List<TeamMember> members = teamMemberRepository.findByProjectId(pid);
        for (TeamMember member : members) {
            if (rid.equals(member.getRole()) || (member.getRoleIds() != null && member.getRoleIds().contains(rid))) {
                List<ResponsibilityItem> responsibilities = member.getResponsibilities();
                if (responsibilities == null) {
                    responsibilities = new ArrayList<>();
                }
                if (checked) {
                    // 勾选：添加职责
                    for (String dutyId : ids) {
                        boolean exists = responsibilities.stream()
                                .anyMatch(r -> dutyId.equals(r.getName()));
                        if (!exists) {
                            responsibilities.add(new ResponsibilityItem(dutyId, true));
                        }
                    }
                } else {
                    // 取消勾选：删除职责
                    responsibilities.removeIf(r -> ids.contains(r.getName()));
                }
                member.setResponsibilities(responsibilities);
                teamMemberRepository.save(member);
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", checked ? "职责勾选成功" : "职责取消成功");
        return result;
    }

    public Map<String, Object> findUserById(String id) {
        // v2 mock数据：根据常见userId返回mock用户信息
        Map<String, Object> user = new HashMap<>();
        user.put("id", id);
        switch (id) {
            case "zhangwei" -> {
                user.put("name", "张伟");
                user.put("deptName", "信息科技部");
                user.put("email", "zhangwei@example.com");
            }
            case "chenjie" -> {
                user.put("name", "陈杰");
                user.put("deptName", "信息科技部");
                user.put("email", "chenjie@example.com");
            }
            case "liming" -> {
                user.put("name", "李明");
                user.put("deptName", "信息科技部");
                user.put("email", "liming@example.com");
            }
            case "wangfang" -> {
                user.put("name", "王芳");
                user.put("deptName", "信息科技部");
                user.put("email", "wangfang@example.com");
            }
            case "maweihua" -> {
                user.put("name", "马伟华");
                user.put("deptName", "信息科技部");
                user.put("email", "maweihua@example.com");
            }
            default -> {
                user.put("name", id);
                user.put("deptName", "信息科技部");
                user.put("email", id + "@example.com");
            }
        }
        return user;
    }

    // ========== V3 接口（mock数据） ==========

    public List<Map<String, Object>> findProjectProgramPlanTreeByProjectId(String projectId) {
        List<ProjectProgramPlan> plans = planRepository.findByProjectIdOrderByParentIdAscSortOrderAsc(projectId);
        return buildPlanTree(plans, null);
    }

    private List<Map<String, Object>> buildPlanTree(List<ProjectProgramPlan> plans, Long parentId) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (ProjectProgramPlan plan : plans) {
            if ((parentId == null && plan.getParentId() == null) ||
                (parentId != null && parentId.equals(plan.getParentId()))) {
                Map<String, Object> node = new HashMap<>();
                node.put("taskNo", plan.getTaskNo());
                node.put("taskName", plan.getTaskName());
                node.put("parentId", plan.getParentId());
                node.put("cutResult", plan.getCutResult());
                node.put("cutResultExplain", plan.getCutResultExplain());
                node.put("children", buildPlanTree(plans, plan.getId()));
                result.add(node);
            }
        }
        return result;
    }

    @Transactional
    public Map<String, Object> savePlanTaskCutResult(List<Map<String, Object>> tasks) {
        if (tasks == null) {
            tasks = Collections.emptyList();
        }
        for (Map<String, Object> task : tasks) {
            String taskNo = (String) task.get("taskNo");
            String cutResult = (String) task.get("cutResult");
            String cutResultExplain = (String) task.get("cutResultExplain");
            if (taskNo != null) {
                planRepository.findAll().stream()
                        .filter(p -> taskNo.equals(p.getTaskNo()))
                        .findFirst()
                        .ifPresent(p -> {
                            p.setCutResult(cutResult);
                            p.setCutResultExplain(cutResultExplain);
                            planRepository.save(p);
                        });
            }
        }
        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "保存成功");
        return result;
    }

    public Map<String, Object> findAssetByProjectProgramPage(String rel, String projectId) {
        List<ProjectDeliverable> deliverables = deliverableRepository.findByProjectId(projectId);
        List<Map<String, Object>> content = new ArrayList<>();
        for (ProjectDeliverable d : deliverables) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", d.getId());
            item.put("name", d.getAssetName());
            item.put("rel", rel);
            item.put("projectId", d.getProjectId());
            item.put("cutResult", d.getCutResult());
            item.put("cutResultExplain", d.getCutResultExplain());
            content.add(item);
        }
        Map<String, Object> result = new HashMap<>();
        result.put("content", content);
        result.put("totalElements", content.size());
        result.put("totalPages", 1);
        result.put("number", 0);
        result.put("size", content.size());
        return result;
    }

    @Transactional
    public Map<String, Object> savePlanTaskRel(List<Map<String, Object>> rel) {
        if (rel == null) {
            rel = Collections.emptyList();
        }
        for (Map<String, Object> item : rel) {
            Object idObj = item.get("id");
            String cutResult = (String) item.get("cutResult");
            String cutResultExplain = (String) item.get("cutResultExplain");
            if (idObj != null) {
                Long id = idObj instanceof Number ? ((Number) idObj).longValue() : Long.parseLong(idObj.toString());
                deliverableRepository.findById(id).ifPresent(d -> {
                    d.setCutResult(cutResult);
                    d.setCutResultExplain(cutResultExplain);
                    deliverableRepository.save(d);
                });
            }
        }
        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "保存成功");
        return result;
    }

    public List<Map<String, Object>> findRelProject(String rel, String projectId) {
        List<RelatedProject> relProjects = relatedProjectRepository.findByProjectId(projectId);
        List<Map<String, Object>> result = new ArrayList<>();
        for (RelatedProject rp : relProjects) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", rp.getRelProjectId());
            item.put("name", rp.getRelProjectId()); // mock: 名称用ID代替
            item.put("rel", rp.getRelType() != null ? rp.getRelType() : rel);
            item.put("projectId", rp.getProjectId());
            result.add(item);
        }
        // 如果没有关联项目，返回mock数据
        if (result.isEmpty()) {
            Map<String, Object> mock = new HashMap<>();
            mock.put("id", "PJ-202603-S-069");
            mock.put("name", "关联项目示例");
            mock.put("rel", rel != null ? rel : "依赖");
            mock.put("projectId", projectId);
            result.add(mock);
        }
        return result;
    }

    // ========== 权限校验 ==========

    /**
     * [MVP] 验证用户是否为项目经理（修复 P0-2 / P0-7）
     * 只有项目经理可以操作AI功能
     */
    public void validateProjectManager(String projectId, String userId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        if (!project.getPmName().equals(userId)) {
            throw new AccessDeniedException("只有项目经理可以操作AI功能");
        }
    }
}
